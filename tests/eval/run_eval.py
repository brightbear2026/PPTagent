"""
run_eval.py — PPTagent 最小 Eval Harness

运行方式（在 Docker 容器内）：
  python3 tests/eval/run_eval.py [--compare baseline.json] [--no-judge] [--fixture quarterly_report]

功能：
  1. 对 fixtures/ 中每个文档运行 parse → analyze → outline（可选：content）
  2. 规则评分（rule_scorer）
  3. LLM-as-judge 评分（llm_judge，可用 --no-judge 跳过）
  4. 输出 JSON 报告，记录 prompt 版本号
  5. 与 baseline.json 对比，打印 delta
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目根到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scorers.rule_scorer import score_outline, score_content
from scorers.llm_judge import judge_outline, judge_content

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

FIXTURES_DIR = Path(__file__).parent / "fixtures"
BASELINE_PATH = Path(__file__).parent / "baseline.json"


def _get_prompt_versions() -> dict:
    """读取 pipeline/prompts/ 下所有文件的版本号。"""
    prompts_dir = Path(__file__).parent.parent.parent / "pipeline" / "prompts"
    versions = {}
    if prompts_dir.exists():
        for f in prompts_dir.glob("*.md"):
            # 文件名格式: analyze_agent.v1.md → {"analyze": "v1"}
            parts = f.stem.split(".")
            if len(parts) >= 2:
                agent = parts[0].replace("_agent", "")
                version = parts[1]
                versions[agent] = version
    return versions


def _build_pipeline_llm():
    """构建 pipeline 用的 LLM client（从环境变量读取配置）。"""
    from llm_client.factory import get_client
    provider = os.environ.get("EVAL_PIPELINE_PROVIDER", "openai_compat")
    model = os.environ.get("EVAL_PIPELINE_MODEL", "deepseek-chat")
    api_key = os.environ.get("EVAL_PIPELINE_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    base_url = os.environ.get("EVAL_PIPELINE_BASE_URL", "https://api.deepseek.com/v1")
    return get_client(provider=provider, model=model, api_key=api_key, base_url=base_url)


def _build_judge_llm():
    """构建 judge 用的 LLM client（与 pipeline 使用不同 provider）。"""
    from llm_client.factory import get_client
    provider = os.environ.get("EVAL_JUDGE_PROVIDER", "openai_compat")
    model = os.environ.get("EVAL_JUDGE_MODEL", "Qwen/Qwen2.5-72B-Instruct")
    api_key = os.environ.get("EVAL_JUDGE_API_KEY", os.environ.get("SILICONFLOW_API_KEY", ""))
    base_url = os.environ.get("EVAL_JUDGE_BASE_URL", "https://api.siliconflow.cn/v1")
    return get_client(provider=provider, model=model, api_key=api_key, base_url=base_url)


def run_fixture(fixture_path: Path, pipeline_llm, judge_llm, skip_judge: bool) -> dict:
    """对单个 fixture 运行 parse → analyze → outline，返回评分结果。"""
    from pipeline.agents.parse_agent import ParseAgent
    from pipeline.agents.analyze_agent import AnalyzeAgent
    from pipeline.agents.plan_agent import PlanAgent

    fixture_name = fixture_path.stem
    logger.info(f"[eval] 处理 fixture: {fixture_name}")

    source_text = fixture_path.read_text(encoding="utf-8")

    # ── Parse ──
    t0 = time.time()
    parse_agent = ParseAgent()
    raw = parse_agent.run({"text": source_text, "task": {"title": fixture_name}})
    logger.info(f"[eval] parse done ({time.time()-t0:.1f}s)")

    # ── Analyze ──
    t0 = time.time()
    analyze_agent = AnalyzeAgent(pipeline_llm)
    noop = lambda p, m: None
    analysis = analyze_agent.run({
        "task": {"title": fixture_name, "target_audience": "管理层", "scenario": "季度汇报"},
        "raw_content": raw,
        "report_progress": noop,
    })
    logger.info(f"[eval] analyze done ({time.time()-t0:.1f}s), chunks={len(analysis.get('chunks',[]))}")

    # ── Outline ──
    t0 = time.time()
    plan_agent = PlanAgent(pipeline_llm)
    outline = plan_agent.run({
        "task": {"title": fixture_name, "target_audience": "管理层", "scenario": "季度汇报", "language": "zh"},
        "analysis": analysis,
        "raw_content": raw,
        "report_progress": noop,
    })
    logger.info(f"[eval] outline done ({time.time()-t0:.1f}s), slides={len(outline.get('items',[]))}")

    # ── Rule scoring ──
    rule_scores = score_outline(outline)

    # ── LLM judge ──
    judge_scores = {}
    if not skip_judge and judge_llm:
        try:
            judge_scores = judge_outline(source_text, outline, judge_llm)
        except Exception as e:
            logger.warning(f"[eval] judge failed for {fixture_name}: {e}")

    return {
        "fixture": fixture_name,
        "slides_count": len(outline.get("items", [])),
        "chunks_count": len(analysis.get("chunks", [])),
        "rule_scores": rule_scores,
        "judge_scores": judge_scores,
    }


def compare_with_baseline(current: dict, baseline: dict) -> dict:
    """计算当前分数与 baseline 的 delta。"""
    deltas = {}
    for fixture_name, cur_data in current.items():
        base_data = baseline.get(fixture_name, {})
        fixture_delta = {}
        for score_type in ("rule_scores", "judge_scores"):
            cur_scores = cur_data.get(score_type, {})
            base_scores = base_data.get(score_type, {})
            for key, cur_val in cur_scores.items():
                if isinstance(cur_val, (int, float)) and key in base_scores:
                    delta = round(cur_val - float(base_scores[key]), 3)
                    fixture_delta[f"{score_type}.{key}"] = delta
        deltas[fixture_name] = fixture_delta
    return deltas


def main():
    parser = argparse.ArgumentParser(description="PPTagent Eval Harness")
    parser.add_argument("--compare", metavar="BASELINE_JSON", help="与此 baseline 文件对比")
    parser.add_argument("--no-judge", action="store_true", help="跳过 LLM-as-judge 评分（节省成本）")
    parser.add_argument("--fixture", metavar="NAME", help="只运行指定 fixture（不含扩展名）")
    parser.add_argument("--write-baseline", action="store_true", help="将当前结果写入 baseline.json")
    args = parser.parse_args()

    # 收集 fixture 文件
    fixtures = sorted(FIXTURES_DIR.glob("*.txt")) + sorted(FIXTURES_DIR.glob("*.md"))
    if args.fixture:
        fixtures = [f for f in fixtures if f.stem == args.fixture]
        if not fixtures:
            print(f"[eval] fixture '{args.fixture}' not found in {FIXTURES_DIR}")
            sys.exit(1)

    if not fixtures:
        print(f"[eval] No fixtures found in {FIXTURES_DIR}")
        sys.exit(1)

    # 构建 LLM clients
    pipeline_llm = _build_pipeline_llm()
    judge_llm = None if args.no_judge else _build_judge_llm()

    # 运行评估
    results = {}
    for fixture_path in fixtures:
        try:
            result = run_fixture(fixture_path, pipeline_llm, judge_llm, skip_judge=args.no_judge)
            results[fixture_path.stem] = result
        except Exception as e:
            logger.error(f"[eval] fixture {fixture_path.stem} failed: {e}")
            results[fixture_path.stem] = {"error": str(e)}

    # 汇总报告
    report = {
        "run_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "prompt_versions": _get_prompt_versions(),
        "scores": results,
    }

    # 打印结果
    print("\n" + "=" * 60)
    print("EVAL RESULTS")
    print("=" * 60)
    for fixture_name, data in results.items():
        if "error" in data:
            print(f"\n[FAIL] {fixture_name}: {data['error']}")
            continue
        print(f"\n[{fixture_name}] slides={data.get('slides_count')}, chunks={data.get('chunks_count')}")
        for k, v in data.get("rule_scores", {}).items():
            print(f"  rule.{k}: {v}")
        for k, v in data.get("judge_scores", {}).items():
            if isinstance(v, (int, float)) and v >= 0:
                print(f"  judge.{k}: {v}")

    # 对比 baseline
    if args.compare:
        baseline_path = Path(args.compare)
        if baseline_path.exists():
            baseline = json.loads(baseline_path.read_text())
            baseline_scores = baseline.get("scores", baseline)
            deltas = compare_with_baseline(results, baseline_scores)
            print("\n" + "=" * 60)
            print("DELTA vs BASELINE")
            print("=" * 60)
            for fixture_name, d in deltas.items():
                print(f"\n[{fixture_name}]")
                for k, v in d.items():
                    sign = "+" if v > 0 else ""
                    flag = " ⬆" if v > 0.05 else (" ⬇" if v < -0.05 else "")
                    print(f"  {k}: {sign}{v}{flag}")
        else:
            print(f"\n[warn] baseline file not found: {args.compare}")

    # 写入 baseline
    if args.write_baseline:
        BASELINE_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\n[eval] baseline written to {BASELINE_PATH}")

    # 写入本次报告到 eval_report_latest.json
    report_path = Path(__file__).parent / "eval_report_latest.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[eval] report saved to {report_path}")


if __name__ == "__main__":
    main()
