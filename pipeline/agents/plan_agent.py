"""
PlanAgent — 替代 OutlineAgent，使用金字塔原理生成论证型大纲。

设计原则：
- PPT是论证序列，不是文档章节目录
- 每张幻灯片传递一个明确的CLAIM（论点），包含动词的完整句子
- 叙事框架由用户选择的 scenario 决定（SCQA/SCR/AIDA等）
- 生成的 items 格式与旧 OutlineAgent 完全兼容，ContentAgent 无需改动

输出格式（与 OutlineResult 兼容）：
{
  "narrative_logic": "框架描述",
  "scqa": {...},
  "items": [OutlineItem dicts...],
  "data_gap_suggestions": []
}
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

from llm_client.base import ChatMessage

logger = logging.getLogger(__name__)

# 场景 → 叙事框架映射（硬编码，用户选择直接生效）
SCENARIO_FRAMEWORK_MAP: Dict[str, tuple] = {
    "季度汇报":  ("scr",              "SCR框架：情境（Situation）→ 行动/挑战（Complication）→ 结论/结果（Resolution）"),
    "战略提案":  ("scqa",             "SCQA框架：情境（S）→ 挑战（C）→ 核心问题（Q）→ 顶层答案/结论（A）"),
    "竞标pitch": ("aida",             "AIDA框架：吸引注意（痛点）→ 激发兴趣（方案价值）→ 激发欲望（利益证据）→ 行动号召（CTA）"),
    "内部分析":  ("issue_tree",       "Issue Tree框架：核心问题 → MECE分解 → 每个叶节点 = 一个发现/结论"),
    "培训材料":  ("explanation",      "解释型框架：目标→现状→差距→方案→评估（ADDIE变体）"),
    "项目汇报":  ("scr",              "STAR框架：情境（Situation）→ 任务（Task）→ 行动（Action）→ 结果（Result）"),
    "产品发布":  ("problem_solution", "问题-方案框架：痛点树（问题）→ 解决方案树（方案+利益）"),
}

# 框架 → 输出结构模板（让 system prompt 的 JSON 格式与叙事框架一致）
FRAMEWORK_STRUCTURES: Dict[str, dict] = {
    "scqa": {
        "field": "scqa",
        "keys": ["situation", "complication", "question", "answer"],
        "labels": ["现状背景", "核心挑战/冲突", "核心问题", "顶层结论"],
        "opener_title": "SCQA开篇：{question}",
    },
    "scr": {
        "field": "scqa",
        "keys": ["situation", "complication", "resolution"],
        "labels": ["情境背景", "挑战/行动", "结论/结果"],
        "opener_title": "开篇：{resolution}",
    },
    "aida": {
        "field": "scqa",
        "keys": ["attention", "interest", "desire", "action"],
        "labels": ["痛点/注意力", "方案价值/兴趣", "利益证据/欲望", "行动号召"],
        "opener_title": "开篇：{attention}",
    },
    "explanation": {
        "field": "scqa",
        "keys": ["objective", "current_state", "gap", "solution", "evaluation"],
        "labels": ["学习/沟通目标", "现状描述", "差距与挑战", "解决方案", "评估与总结"],
        "opener_title": "开篇：{objective}",
    },
    "issue_tree": {
        "field": "scqa",
        "keys": ["core_question", "decomposition_logic", "key_finding"],
        "labels": ["核心问题", "分解逻辑", "关键发现"],
        "opener_title": "开篇：{core_question}",
    },
    "problem_solution": {
        "field": "scqa",
        "keys": ["problem_statement", "solution_statement"],
        "labels": ["痛点/问题陈述", "解决方案陈述"],
        "opener_title": "开篇：{problem_statement}",
    },
}

SLIDE_ROLE_TO_NARRATIVE_ARC = {
    "cover":       "opening",
    "opener":      "opening",
    "section":     "context",
    "key_message": "solution",
    "evidence":    "evidence",
    "summary":     "recommendation",
    "cta":         "closing",
}

SLIDE_ROLE_TO_TYPE = {
    "cover":       "title",
    "opener":      "content",
    "section":     "content",
    "key_message": "content",
    "evidence":    "data",
    "summary":     "summary",
    "cta":         "content",
}


class PlanAgent:
    """
    论证型大纲生成 Agent。

    直接调用 LLM（无 ReAct 工具循环），使用：
    1. 金字塔原理系统 prompt
    2. 用户选择的场景 → 叙事框架
    3. 文档 chunks 作为证据基础
    4. 内置 rule-based 验证 + 最多1次 LLM 修复
    """

    MAX_TOKENS = 6000
    TEMPERATURE = 0.5
    MAX_VERIFY_RETRIES = 1

    def __init__(self, llm_client):
        self.llm = llm_client

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------

    def run(self, context: Dict[str, Any]) -> Dict:
        report = context.get("report_progress", lambda p, m: None)

        task = context.get("task", {})
        analysis = context.get("analysis", {})
        raw = context.get("raw_content", {})

        scenario = task.get("scenario", "")
        target_audience = task.get("target_audience", "管理层")
        title = task.get("title", "")
        language = task.get("language", "zh")

        chunks = analysis.get("chunks", [])
        # 如果 analyze 阶段没有 chunks（旧版本），从 raw_content 现场构建
        if not chunks:
            chunks = self._build_chunks_from_raw(raw)

        report(32, "正在构建论证框架...")
        result = self._generate_plan(
            title=title,
            scenario=scenario,
            target_audience=target_audience,
            language=language,
            analysis=analysis,
            chunks=chunks,
            raw=raw,
        )

        report(47, f"大纲生成完成：共{len(result.get('items', []))}页")
        return result

    # ------------------------------------------------------------------
    # 核心生成逻辑
    # ------------------------------------------------------------------

    def _generate_plan(
        self,
        title: str,
        scenario: str,
        target_audience: str,
        language: str,
        analysis: Dict,
        chunks: List[Dict],
        raw: Dict,
    ) -> Dict:
        framework_arc, framework_desc = SCENARIO_FRAMEWORK_MAP.get(
            scenario, ("", "根据文档内容自主选择最合适的叙事框架（SCR/SCQA/Problem-Solution）")
        )

        system_msg = self._build_system_prompt(framework_desc, framework_arc)
        user_msg = self._build_user_prompt(
            title=title,
            scenario=scenario,
            target_audience=target_audience,
            language=language,
            analysis=analysis,
            chunks=chunks,
            raw=raw,
            framework_arc=framework_arc,
        )

        messages = [
            ChatMessage(role="system", content=system_msg),
            ChatMessage(role="user", content=user_msg),
        ]

        response = self.llm.chat(
            messages=messages,
            temperature=self.TEMPERATURE,
            max_tokens=self.MAX_TOKENS,
        )

        if not response.success:
            raise RuntimeError(f"LLM调用失败: {response.error}")

        raw_output = response.content or ""
        plan_data = self._parse_plan_json(raw_output)

        # Rule-based verify + one-shot fix
        issues = self._verify_plan(plan_data, chunks, framework_arc)
        if issues and self.MAX_VERIFY_RETRIES > 0:
            logger.warning("[PlanAgent] 验证发现问题，尝试LLM修复: %s", issues)
            plan_data = self._fix_plan(messages, plan_data, issues, chunks)

        return self._to_outline_result(plan_data, scenario, framework_desc, chunks)

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def _build_system_prompt(self, framework_desc: str, framework_arc: str) -> str:
        from .base import load_prompt

        arc_constraint = ""
        if framework_arc:
            arc_constraint = f'\n- narrative_arc 字段使用: "{framework_arc}"（用户已选定场景，不可更改）'

        struct = FRAMEWORK_STRUCTURES.get(framework_arc, FRAMEWORK_STRUCTURES["scqa"])
        struct_lines = []
        for key, label in zip(struct["keys"], struct["labels"]):
            struct_lines.append(f'    "{key}": "{label}（1-2句）"')
        struct_json = ",\n".join(struct_lines)

        last_key = struct["keys"][-1]

        template = load_prompt("plan_agent", "v1")
        return (template
                .replace("<<FRAMEWORK_DESC>>", framework_desc)
                .replace("<<ARC_CONSTRAINT>>", arc_constraint)
                .replace("<<STRUCT_JSON>>", struct_json)
                .replace("<<LAST_KEY>>", last_key))

    def _build_user_prompt(
        self,
        title: str,
        scenario: str,
        target_audience: str,
        language: str,
        analysis: Dict,
        chunks: List[Dict],
        raw: Dict,
        framework_arc: str,
    ) -> str:
        strategy = analysis.get("strategy", {})
        doc_summary = strategy.get("document_summary", "")
        core_themes = strategy.get("core_themes", [])
        key_messages = strategy.get("key_messages", [])
        page_range = strategy.get("recommended_page_range", "12-18页")

        # 章节结构（source_pages 摘要）
        source_pages = raw.get("source_pages", [])
        section_lines = []
        for i, sp in enumerate(source_pages[:20]):
            sec_title = sp.get("title", "")
            content = sp.get("content", "")
            excerpt = content[:120].replace("\n", " ").strip()
            excerpt_str = f"：{excerpt}…" if excerpt else ""
            section_lines.append(f"  [{i+1}] {sec_title}（{len(content)}字）{excerpt_str}")
        sections_text = "\n".join(section_lines) if section_lines else "（无结构化章节）"

        # 表格清单
        tables = raw.get("_tables", [])
        table_lines = [
            f"  表格{i+1}: {t.get('source_sheet', '表格')}（{len(t.get('rows', []))}行）"
            f" 字段: {', '.join(str(h) for h in t.get('headers', [])[:5])}"
            for i, t in enumerate(tables[:6])
        ]
        tables_text = "\n".join(table_lines) if table_lines else "（无数据表格）"

        # Chunk ID 参考列表（按 section 均匀采样，防止长文档后半段被截断）
        sampled_chunks = self._sample_chunks(chunks)
        chunk_ref_lines = [
            f"  [{c['id']}] [{c['section']}] {c['text'][:100]}…"
            for c in sampled_chunks
        ]
        chunks_text = "\n".join(chunk_ref_lines) if chunk_ref_lines else "（无 chunk 数据）"

        arc_note = f"\n**指定叙事框架**: {framework_arc}（narrative_arc 字段必须使用此值）" if framework_arc else ""

        return f"""请为以下材料生成PPT大纲。

## 任务信息
- **PPT标题**: {title}
- **目标受众**: {target_audience}
- **汇报场景**: {scenario or "通用汇报"}{arc_note}
- **推荐页数**: {page_range}
- **语言**: {"中文" if language == "zh" else "English"}

## 文档分析结论
**文档摘要**: {doc_summary}

**核心主题**:
{chr(10).join(f"  - {t}" for t in core_themes)}

**关键信息（这些必须在幻灯片中体现）**:
{chr(10).join(f"  - {m}" for m in key_messages)}

## 文档章节结构（共{len(source_pages)}个章节）
{sections_text}

## 数据表格（共{len(tables)}个）
{tables_text}

## 文档 Chunk 参考（supporting_hint 从这里选取章节名）
{chunks_text}

---
请严格按照系统提示中的 JSON 格式输出大纲。记住：
- 每个 content/data 页的 takeaway_message 必须是含动词的完整句子
- 幻灯片顺序是论证逻辑，不是文档章节顺序
- supporting_hint 填写上方章节列表中的具体章节名
- chunk_ids 从上方"文档 Chunk 参考"中选取相关 id，title/agenda 页留空列表"""

    # ------------------------------------------------------------------
    # Chunk 采样（按 section 均匀采样，避免长文档截断）
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_chunks(chunks: List[Dict], max_per_section: int = 5) -> List[Dict]:
        """按 section 均匀采样 chunks，每 section 最多 max_per_section 个。"""
        from collections import defaultdict
        section_buckets: dict = defaultdict(list)
        for c in chunks:
            section_buckets[c.get("section", "_default")].append(c)

        sampled = []
        for sec_chunks in section_buckets.values():
            step = max(1, len(sec_chunks) // max_per_section)
            sampled.extend(sec_chunks[::step][:max_per_section])
        return sampled

    # ------------------------------------------------------------------
    # JSON 解析
    # ------------------------------------------------------------------

    def _parse_plan_json(self, text: str) -> Dict:
        patterns = [
            r'```json\s*(\{[\s\S]*?\})\s*```',
            r'```\s*(\{[\s\S]*?\})\s*```',
            r'(\{[\s\S]*"slides"[\s\S]*\})',
            r'(\{[\s\S]*"scqa"[\s\S]*\})',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, dict) and ("slides" in data or "scqa" in data):
                        return data
                except Exception:
                    continue

        logger.error("[PlanAgent] 无法从LLM输出解析JSON，使用兜底大纲")
        return self._fallback_plan()

    # ------------------------------------------------------------------
    # 验证
    # ------------------------------------------------------------------

    def _verify_plan(self, plan: Dict, chunks: List[Dict], framework_arc: str = "scqa") -> List[str]:
        issues = []
        slides = plan.get("slides", [])

        if len(slides) < 4:
            issues.append(f"幻灯片数量过少（{len(slides)}页），至少需要4页")

        if not any(s.get("slide_type") == "title" for s in slides):
            issues.append("缺少封面页（slide_type=title），请在第1页添加封面")

        content_slides = [s for s in slides if s.get("slide_type") not in ("title", "section_divider")]
        for s in content_slides:
            tm = s.get("takeaway_message", "")
            if tm and not re.search(r'[一-龥a-zA-Z]{2}', tm):
                issues.append(f"takeaway_message 过短或无内容: P{s.get('page_number')}")
            if tm and len(tm) < 8 and s.get("slide_type") in ("content", "data", "diagram"):
                issues.append(f"P{s.get('page_number')} takeaway_message 可能是名词短语，应为完整句子: {tm!r}")

        scqa = plan.get("scqa", {})
        struct = FRAMEWORK_STRUCTURES.get(framework_arc, FRAMEWORK_STRUCTURES["scqa"])
        last_key = struct["keys"][-1]
        if not scqa.get(last_key):
            issues.append(f"scqa.{last_key}（顶层结论）为空")

        return issues

    # ------------------------------------------------------------------
    # 一次修复
    # ------------------------------------------------------------------

    def _fix_plan(
        self,
        original_messages: List[ChatMessage],
        plan: Dict,
        issues: List[str],
        chunks: List[Dict],
    ) -> Dict:
        fix_messages = list(original_messages)
        fix_messages.append(ChatMessage(
            role="assistant",
            content=f"```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```",
        ))
        issue_text = "\n".join(f"- {i}" for i in issues)
        fix_messages.append(ChatMessage(
            role="user",
            content=(
                f"输出存在以下问题，请修正后重新输出完整 JSON：\n{issue_text}\n\n"
                "特别注意：content/data 页的 takeaway_message 必须是含动词的完整句子，"
                "而不是名词短语（例如：不能写【数据分析】，应写【数据显示用户增速连续三季度加快】）。"
            ),
        ))

        response = self.llm.chat(
            messages=fix_messages,
            temperature=self.TEMPERATURE,
            max_tokens=self.MAX_TOKENS,
        )
        if response.success and response.content:
            fixed = self._parse_plan_json(response.content)
            if fixed.get("slides"):
                return fixed
        return plan

    # ------------------------------------------------------------------
    # 转换为 OutlineResult 兼容格式
    # ------------------------------------------------------------------

    def _to_outline_result(
        self, plan: Dict, scenario: str, framework_desc: str, chunks: Optional[List[Dict]] = None
    ) -> Dict:
        slides = plan.get("slides", [])

        # Whitelist-filter chunk_ids: remove any ids the LLM invented
        if chunks:
            valid_ids = {c["id"] for c in chunks if c.get("id")}
            for s in slides:
                raw_ids = s.get("chunk_ids", [])
                s["chunk_ids"] = [cid for cid in raw_ids if cid in valid_ids]
        scqa = plan.get("scqa", {})

        # Extract root_claim: try explicit field, then last structure key, then any value
        arc, _ = SCENARIO_FRAMEWORK_MAP.get(scenario, ("", framework_desc))
        struct = FRAMEWORK_STRUCTURES.get(arc, FRAMEWORK_STRUCTURES["scqa"])
        root_claim = plan.get("root_claim", "")
        if not root_claim:
            # Try each key in reverse order to find a non-empty value
            for key in reversed(struct["keys"]):
                val = scqa.get(key, "")
                if val:
                    root_claim = val
                    break

        # Ensure at least one title slide exists as the first slide
        has_title_slide = any(s.get("slide_type") == "title" for s in slides)
        if not has_title_slide:
            slides.insert(0, {
                "page_number": 1,
                "slide_type": "title",
                "title": root_claim or "演示文稿",
                "takeaway_message": "",
                "supporting_hint": "",
                "data_source": "",
                "primary_visual": "text_only",
                "narrative_arc": "opening",
                "section": "",
            })

        # Normalize page numbers
        for i, s in enumerate(slides, 1):
            s["page_number"] = i

        # Build narrative_logic string for frontend display
        _, desc = SCENARIO_FRAMEWORK_MAP.get(scenario, ("", framework_desc))
        if root_claim:
            narrative_logic = f"{desc} | 顶层结论: {root_claim}"
        else:
            narrative_logic = desc or framework_desc

        # Ensure required fields
        for s in slides:
            s.setdefault("supporting_hint", "")
            s.setdefault("data_source", "")
            s.setdefault("primary_visual", "text_only")
            s.setdefault("narrative_arc", "evidence")
            s.setdefault("section", "")
            s.setdefault("title", s.get("takeaway_message", ""))
            # section dividers have no takeaway
            if s.get("slide_type") == "section_divider":
                s["takeaway_message"] = s.get("takeaway_message") or s.get("title", "")
                s["primary_visual"] = "text_only"

        # ── Auto-inject agenda + section_divider slides ───────────────────────
        _structural = {"agenda", "section_divider"}

        # Strip any structural slides the LLM accidentally generated
        slides = [s for s in slides if s.get("slide_type") not in _structural]

        # Collect unique section names in order of first appearance (skip title slides)
        sections_order: list = []
        for s in slides:
            if s.get("slide_type") == "title":
                continue
            sec = s.get("section", "").strip()
            if sec and sec not in sections_order:
                sections_order.append(sec)

        # Only inject when there are 2 or more distinct chapters
        if len(sections_order) >= 2:
            title_slides = [s for s in slides if s.get("slide_type") == "title"]
            content_slides = [s for s in slides if s.get("slide_type") != "title"]

            agenda_slide = {
                "slide_type": "agenda", "title": "目录", "takeaway_message": "目录",
                "supporting_hint": "", "data_source": "", "primary_visual": "text_only",
                "narrative_arc": "opening", "section": "",
            }

            rebuilt: list = []
            for sec in sections_order:
                rebuilt.append({
                    "slide_type": "section_divider", "title": sec, "takeaway_message": sec,
                    "supporting_hint": "", "data_source": "", "primary_visual": "text_only",
                    "narrative_arc": "context", "section": sec,
                })
                rebuilt.extend(s for s in content_slides if s.get("section", "").strip() == sec)

            # Slides without a section assignment go at the end
            rebuilt.extend(s for s in content_slides if not s.get("section", "").strip())

            slides = title_slides + [agenda_slide] + rebuilt

        # Final page renumber after all injections
        for i, s in enumerate(slides, 1):
            s["page_number"] = i

        return {
            "narrative_logic": narrative_logic,
            "scqa": scqa,
            "root_claim": root_claim,
            "items": slides,
            "data_gap_suggestions": [],
        }

    # ------------------------------------------------------------------
    # 兜底：当LLM输出完全无法解析时
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_plan() -> Dict:
        return {
            "scqa": {
                "situation": "文档内容已分析",
                "complication": "需要结构化呈现",
                "question": "如何有效传达核心观点？",
                "answer": "通过结构化演示文稿系统呈现分析结论",
            },
            "root_claim": "通过结构化演示文稿系统呈现分析结论",
            "slides": [
                {"page_number": 1, "slide_type": "title", "title": "演示文稿",
                 "takeaway_message": "", "supporting_hint": "", "data_source": "",
                 "primary_visual": "text_only", "narrative_arc": "opening", "section": ""},
                {"page_number": 2, "slide_type": "content", "title": "核心结论",
                 "takeaway_message": "本次分析提供了系统化的决策依据和行动建议",
                 "supporting_hint": "", "data_source": "",
                 "primary_visual": "visual_block", "narrative_arc": "resolution", "section": ""},
                {"page_number": 3, "slide_type": "summary", "title": "总结",
                 "takeaway_message": "行动建议与后续步骤",
                 "supporting_hint": "", "data_source": "",
                 "primary_visual": "text_only", "narrative_arc": "closing", "section": ""},
            ],
        }

    # ------------------------------------------------------------------
    # 从 raw_content 构建 chunks（向后兼容，当 analyze 阶段未生成 chunks 时）
    # ------------------------------------------------------------------

    @staticmethod
    def _build_chunks_from_raw(raw: Dict) -> List[Dict]:
        from pipeline.agents.analyze_agent import AnalyzeAgent
        source_pages = raw.get("source_pages", [])
        return AnalyzeAgent._chunk_document(source_pages)
