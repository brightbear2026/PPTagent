"""
OutlineAgent — ReActAgent
生成PPT页面大纲（检查点1）。

工具：
  - read_strategy(): 读取analyze阶段的策略分析
  - read_metrics(): 读取派生指标
  - read_section(section_title, max_chars): 读取原文章节
  - read_table_preview(table_index): 预览表格数据
  - check_visual_rhythm(items_json): 检查视觉节奏约束
  - submit_outline(slides_json): 提交最终大纲

输出：OutlineResult.to_dict()
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from .base import ReActAgent, Tool, ValidationResult
from llm_client.base import ChatMessage

logger = logging.getLogger(__name__)

VALID_SLIDE_TYPES = {"title", "content", "data", "diagram", "summary", "transition"}
VALID_PRIMARY_VISUALS = {"text", "chart", "diagram", "table", "image", "none"}


class OutlineAgent(ReActAgent):
    """
    大纲生成 Agent。

    先用现有的 OutlineGenerator（已有完整逻辑）生成初稿，
    再通过 ReAct 循环验证和调整，确保视觉节奏和约束满足。
    """

    max_iterations = 3
    max_validation_retries = 2
    temperature = 0.5
    max_tokens = 4096

    def __init__(self, llm_client):
        super().__init__(llm_client)
        self._context: Dict[str, Any] = {}
        self._submitted_outline: Dict = {}

    @property
    def system_prompt(self) -> str:
        return """你是专业PPT大纲设计师。用户消息中已给出建议结构骨架，你的任务是将其展开为完整大纲。

直接输出 JSON 数组，放在 ```json ... ``` 代码块中。不要解释，直接输出 JSON。

每页格式：
{"page_number":1,"slide_type":"title","title":"标题文字","takeaway":"核心结论一句话","primary_visual":"none","section":"所属章节","narrative_arc":"opening","supporting_hint":"参考原文哪个章节（无则留空）","data_source":"使用哪个表格（无则留空）"}

slide_type: "title"|"content"|"data"|"diagram"|"summary"|"transition"
primary_visual: "text"|"chart"|"diagram"|"table"|"image"|"none"
narrative_arc: "opening"|"context"|"problem_statement"|"evidence"|"analysis"|"comparison"|"solution"|"recommendation"|"closing"
  - 封面=opening，背景/现状页=context，问题/挑战页=problem_statement
  - 数据/分析页=evidence 或 analysis，对比页=comparison
  - 方案/路径页=solution，建议/行动页=recommendation，总结页=closing

规则（系统会自动修正不合规项，但请尽量遵守）：
- P1 是封面(title)，最后一页是总结(summary)
- chart 页对应 slide_type="data"，diagram 页对应 slide_type="diagram"
- data 页的 data_source 必须填写对应表格名称
- 相邻页 primary_visual 尽量多样化"""

    @property
    def tools(self) -> List[Tool]:
        # 不使用工具调用 — 直接让 LLM 输出 JSON 文本，通过 extract_output 解析
        return []

    def build_initial_messages(self, context: Dict[str, Any]) -> List[ChatMessage]:
        self._context = context
        task = context.get("task", {})
        raw = context.get("raw_content", {})
        analysis = context.get("analysis", {})
        strategy = analysis.get("strategy", {})

        target_audience = task.get("target_audience", "管理层")
        scenario = task.get("scenario", "")
        title = task.get("title", "")

        # 策略摘要
        core_themes = strategy.get("core_themes", [])
        recommended_structure = strategy.get("recommended_structure", "")
        recommended_page_range = strategy.get("recommended_page_range", "12-18页")
        doc_summary = strategy.get("document_summary", "")

        # 文档章节列表（附首段摘要，让LLM了解各章节实际内容）
        source_pages = raw.get("source_pages", [])
        sections_text = ""
        if source_pages:
            section_lines = []
            for sp in source_pages[:25]:
                title = sp.get("title", "")
                content = sp.get("content", "")
                excerpt = content[:120].replace("\n", " ").strip()
                if excerpt:
                    excerpt = f"：{excerpt}…"
                section_lines.append(f"  - {title}（{len(content)}字）{excerpt}")
            sections_text = "\n".join(section_lines)

        # 表格清单
        tables = raw.get("_tables", [])
        tables_text = ""
        if tables:
            table_lines = [f"  - 表格{i}: {t.get('source_sheet','表格')} ({len(t.get('rows',[]))}行, 字段: {', '.join(t.get('headers',[])[:4])})"
                           for i, t in enumerate(tables[:5])]
            tables_text = "\n".join(table_lines)

        themes_text = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(core_themes))

        key_messages = strategy.get("key_messages", [])
        key_messages_text = "\n".join(f"  - {m}" for m in key_messages)

        audience_analysis = strategy.get("audience_analysis", "")
        scenario_strategy = strategy.get("scenario_strategy", "")

        # 从 recommended_structure 生成骨架，让 LLM "补全"而非"从零创作"
        skeleton = self._build_outline_skeleton(recommended_structure, recommended_page_range)

        user_msg = f"""请将以下建议骨架展开为完整PPT大纲。

**汇报标题**: {title or "（请根据内容确定）"}
**目标受众**: {target_audience}
**汇报场景**: {scenario or "通用汇报"}

## 策略背景
**文档总结**: {doc_summary}
**受众分析**: {audience_analysis}
**叙事策略**: {scenario_strategy}
**核心主题**: {', '.join(core_themes)}
**关键信息**: {'; '.join(key_messages)}

## 文档章节（共{len(source_pages)}个）
{sections_text or "  （无结构化章节）"}

## 数据表格（共{len(tables)}个）
{tables_text or "  （无数据表格）"}

## 建议骨架（请在此基础上展开，为每页补充 title 和 takeaway）
{skeleton}

---
请直接输出完整 JSON 数组，放在 ```json ... ``` 代码块中。
每页须包含: page_number, slide_type, title（≤15字）, takeaway（核心结论一句话）, primary_visual, section
- narrative_arc: 该页在故事中的角色（见上方说明，每页必填）
- supporting_hint: 填写本页主要参考的文档章节名称（如"销售数据分析"），无关联章节则留空
- data_source: data/chart 页填写对应表格名（如"财务汇总表"），其他页留空"""

        return [ChatMessage(role="user", content=user_msg)]

    def extract_output(self, messages: List[ChatMessage]) -> Dict:
        if self._submitted_outline:
            return self._submitted_outline

        # 回退：从 LLM 文本回复中提取 JSON
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.content:
                slides = self._parse_slides_from_text(msg.content)
                if slides:
                    logger.info(f"[OutlineAgent] 从文本回复中提取到{len(slides)}页大纲")
                    self._tool_submit_outline(slides)
                    return self._submitted_outline

        raise ValueError("未找到 submit_outline 调用，请确认 Agent 已提交大纲")

    @staticmethod
    def _clean_json_string(s: str) -> str:
        """去掉行注释和尾逗号，提高 json.loads 成功率"""
        import re
        s = re.sub(r'//[^\n]*', '', s)           # 去掉 // 行注释
        s = re.sub(r',(\s*[\]\}])', r'\1', s)    # 去掉尾逗号
        return s

    @staticmethod
    def _parse_slides_from_text(text: str) -> list:
        """从 LLM 文本中提取 JSON 大纲数组"""
        import re
        patterns = [
            r'```json\s*(\[[\s\S]*?\])\s*```',
            r'```\s*(\[[\s\S]*?\])\s*```',
            r'(\[[\s\S]*"slide_type"[\s\S]*?\])',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                raw = match.group(1)
                for candidate in (raw, OutlineAgent._clean_json_string(raw)):
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, list) and data and isinstance(data[0], dict):
                            if "slide_type" in data[0] or "page_number" in data[0]:
                                return data
                    except Exception:
                        continue
        return []

    def validate(self, output: Dict) -> ValidationResult:
        errors = []
        slides = output.get("items", output.get("slides", []))

        if not slides:
            errors.append("大纲为空")
            return ValidationResult(valid=False, errors=errors)

        if len(slides) < 3:
            errors.append(f"大纲页数{len(slides)}过少，至少需要3页")
            return ValidationResult(valid=False, errors=errors)

        # ── 逐页自动修正（不触发重试）──
        for i, slide in enumerate(slides):
            if slide.get("slide_type") not in VALID_SLIDE_TYPES:
                slide["slide_type"] = "content"
            if slide.get("primary_visual") not in VALID_PRIMARY_VISUALS:
                slide["primary_visual"] = "text"

            pv = slide["primary_visual"]
            st = slide["slide_type"]
            if pv == "chart" and st != "data":
                slide["slide_type"] = "data"
            if pv == "diagram" and st != "diagram":
                slide["slide_type"] = "diagram"

        # ── 首尾页自动修正 ──
        slides[0]["slide_type"] = "title"
        slides[0]["primary_visual"] = "none"
        if len(slides) > 1:
            slides[-1]["slide_type"] = "summary"

        # ── 连续 visual 自动修正（把中间那页改成 text/content）──
        for i in range(1, len(slides) - 1):
            pv_prev = slides[i - 1].get("primary_visual", "text")
            pv_curr = slides[i].get("primary_visual", "text")
            pv_next = slides[i + 1].get("primary_visual", "text")
            if pv_curr == pv_prev == pv_next and pv_curr not in ("none", "text"):
                slides[i]["primary_visual"] = "text"
                if slides[i].get("slide_type") in ("data", "diagram"):
                    slides[i]["slide_type"] = "content"

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def run(self, context: Dict[str, Any]) -> Dict:
        self._submitted_outline = {}
        self._context = context
        return super().run(context)

    # ------------------------------------------------------------------
    # 工具函数
    # ------------------------------------------------------------------

    @staticmethod
    def _build_outline_skeleton(recommended_structure: str, recommended_page_range: str) -> str:
        """
        将 AnalyzeAgent 输出的推荐结构和页数范围转换为带页号的骨架字符串。
        例："开篇→问题→分析→方案→行动" + "12-18页"
        → P1:[title]封面  P2:[content]开篇  ...  Pn:[summary]总结
        """
        import re

        # 解析目标页数（取中间值）
        match = re.search(r'(\d+)\s*[-–~]\s*(\d+)', recommended_page_range)
        if match:
            lo, hi = int(match.group(1)), int(match.group(2))
            target = (lo + hi) // 2
        else:
            digits = re.findall(r'\d+', recommended_page_range)
            target = int(digits[0]) if digits else 14

        target = max(6, min(target, 25))

        # 解析结构段落
        parts = [p.strip() for p in re.split(r'[→➜>>\-–/、,，]+', recommended_structure) if p.strip()]
        if not parts:
            parts = ["开篇", "分析", "结论"]

        # 分配页数：首页 title(1) + 末页 summary(1) + 中间按段落平均分配
        inner_count = target - 2  # 去掉首尾
        inner_count = max(inner_count, len(parts))

        # 每段分配几页
        base, rem = divmod(inner_count, len(parts))
        alloc = [base + (1 if i < rem else 0) for i in range(len(parts))]

        # slide_type 启发规则
        DATA_KEYWORDS = {"数据", "指标", "分析", "财务", "销售", "增长", "收入", "趋势", "对比", "业绩"}
        DIAGRAM_KEYWORDS = {"框架", "流程", "路线图", "架构", "方案", "体系", "模型", "结构", "逻辑"}
        TRANSITION_KEYWORDS = {"过渡", "引言", "背景", "铺垫"}

        def _infer_type(section_name: str) -> str:
            if any(k in section_name for k in DATA_KEYWORDS):
                return "data"
            if any(k in section_name for k in DIAGRAM_KEYWORDS):
                return "diagram"
            if any(k in section_name for k in TRANSITION_KEYWORDS):
                return "transition"
            return "content"

        lines = []
        page = 1

        # 封面
        lines.append(f"P{page}: [title] 封面")
        page += 1

        # 中间段落
        for i, (part, count) in enumerate(zip(parts, alloc)):
            slide_type = _infer_type(part)
            for j in range(count):
                if j == 0:
                    lines.append(f"P{page}: [{slide_type}] {part}")
                else:
                    lines.append(f"P{page}: [{slide_type}] {part}（续{j}）")
                page += 1

        # 末页
        lines.append(f"P{page}: [summary] 总结与行动建议")

        return "\n".join(lines)

    def _tool_read_strategy(self) -> str:
        analysis = self._context.get("analysis", {})
        strategy = analysis.get("strategy", {})

        if not strategy:
            return "未找到策略分析结果"

        lines = ["=== 策略分析结果 ==="]
        lines.append(f"\n【文档总结】\n{strategy.get('document_summary', '')}")
        lines.append(f"\n【受众分析】\n{strategy.get('audience_analysis', '')}")
        lines.append(f"\n【叙事策略】\n{strategy.get('scenario_strategy', '')}")
        lines.append(f"\n【建议结构】\n{strategy.get('recommended_structure', '')}")
        lines.append(f"\n【建议页数】{strategy.get('recommended_page_range', '12-18页')}")
        themes = strategy.get("core_themes", [])
        if themes:
            lines.append("\n【核心主题】")
            for t in themes:
                lines.append(f"  - {t}")
        msgs = strategy.get("key_messages", [])
        if msgs:
            lines.append("\n【关键信息】")
            for m in msgs:
                lines.append(f"  - {m}")

        return "\n".join(lines)

    def _tool_read_metrics(self) -> str:
        analysis = self._context.get("analysis", {})
        metrics = analysis.get("derived_metrics", [])
        findings = analysis.get("key_findings", [])

        lines = ["=== 派生指标 ==="]
        if metrics:
            for m in metrics[:10]:
                if isinstance(m, dict):
                    lines.append(f"  {m.get('name','')}: {m.get('value','')} ({m.get('metric_type','')})")
        else:
            lines.append("  无派生指标")

        if findings:
            lines.append("\n=== 关键发现 ===")
            for f in findings[:8]:
                lines.append(f"  - {f}")

        return "\n".join(lines)

    def _tool_read_section(self, section_title: str, max_chars: int = 1500) -> str:
        raw = self._context.get("raw_content", {})
        for sp in raw.get("source_pages", []):
            if section_title.lower() in (sp.get("title") or "").lower():
                content = sp.get("content", "")
                return f"【{sp['title']}】\n{content[:max_chars]}"
        return f"未找到章节 '{section_title}'"

    def _tool_read_table_preview(self, table_index: int) -> str:
        raw = self._context.get("raw_content", {})
        tables = raw.get("_tables", [])
        if table_index >= len(tables):
            return f"表格{table_index}不存在（共{len(tables)}个）"
        t = tables[table_index]
        headers = t.get("headers", [])
        rows = t.get("rows", [])
        lines = [f"表格{table_index}: {t.get('source_sheet', '')}", f"列: {' | '.join(str(h) for h in headers)}"]
        for row in rows[:5]:
            lines.append("  " + " | ".join(str(c) for c in row[:8]))
        if len(rows) > 5:
            lines.append(f"  ... 共{len(rows)}行")
        return "\n".join(lines)

    def _tool_check_visual_rhythm(self, slides_json: str) -> str:
        try:
            slides = json.loads(slides_json)
        except json.JSONDecodeError as e:
            return f"JSON解析失败: {e}"

        violations = []

        for i in range(len(slides) - 2):
            pvs = [slides[i + j].get("primary_visual", "text") for j in range(3)]
            if len(set(pvs)) == 1 and pvs[0] != "none":
                violations.append(f"第{i+1}~{i+3}页连续相同 primary_visual='{pvs[0]}'")

        content = [s for s in slides if s.get("slide_type") != "title"]
        visual = [s for s in content if s.get("primary_visual") in ("chart", "diagram")]
        ratio = len(visual) / len(content) if content else 0
        if ratio < 0.30:
            violations.append(f"chart+diagram占比{ratio:.0%}，建议≥30%（当前{len(visual)}/{len(content)}页）")

        for s in slides:
            pv = s.get("primary_visual", "")
            st = s.get("slide_type", "")
            if pv == "chart" and st != "data":
                violations.append(f"第{s.get('page_number','?')}页: primary_visual='chart' 但 slide_type='{st}'，应为'data'")
            if pv == "diagram" and st != "diagram":
                violations.append(f"第{s.get('page_number','?')}页: primary_visual='diagram' 但 slide_type='{st}'，应为'diagram'")

        if violations:
            return "发现以下视觉节奏问题：\n" + "\n".join(f"  - {v}" for v in violations)
        return f"视觉节奏检查通过！共{len(slides)}页，chart+diagram占比{ratio:.0%}"

    def _tool_submit_outline(self, slides: List[Dict]) -> str:
        # 标准化页码并转换为 OutlineResult.to_dict() 格式
        items = []
        for i, s in enumerate(slides):
            page_number = i + 1
            items.append({
                "page_number": page_number,
                "slide_type": s.get("slide_type", "content"),
                "takeaway_message": s.get("takeaway", s.get("takeaway_message", "")),
                "supporting_hint": s.get("notes", s.get("supporting_hint", "")),
                "data_source": s.get("data_source", ""),
                "primary_visual": s.get("primary_visual", "text"),
                "narrative_arc": s.get("narrative_arc", ""),
                # 保留额外字段供前端使用
                "title": s.get("title", ""),
                "section": s.get("section", ""),
            })

        self._submitted_outline = {
            "narrative_logic": "Agent生成的大纲",
            "items": items,
            "data_gap_suggestions": [],
            # 兼容字段
            "slides": slides,
        }
        content_count = sum(1 for s in items if s.get("slide_type") != "title")
        return f"大纲已提交：共{len(items)}页，{content_count}个内容页"
