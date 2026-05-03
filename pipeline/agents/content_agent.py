"""
ContentAgent — per-slide 并行内容生成（StructuredLLMAgent）
每个大纲页面独立调用 LLM，最多 MAX_CONCURRENT 并发。

优势：
- 单页 ≤1800 token 输出，finish_reason=length 几乎不触发
- 单页失败只影响该页，不影响其他页面
- _generate_one_slide 可直接复用于 /rerun-page，消除重复代码
"""

from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from .base import StructuredLLMAgent, ValidationResult, load_prompt
from models.schemas import ContentResultSchema, ContentSlideSchema, ParseResult
from models.schema_adapter import (
    content_schema_to_dict,
    degrade_to_text_only,
    make_placeholder,
    parse_slide,
)
from models.slide_spec import PrimaryVisualType, SlideType
from llm_client.base import ChatMessage

logger = logging.getLogger(__name__)


class ContentAgent(StructuredLLMAgent):
    """
    内容填充 Agent — per-slide 并行架构。

    每个 PPT 页面独立调用 LLM，MAX_CONCURRENT 并发上限。
    消除批次 JSON 截断风险；单页失败不影响其他页面。
    """

    MAX_CONCURRENT = 4
    temperature = 0.6
    max_tokens = 3000  # 单页输出，足够容纳丰富内容

    def __init__(self, llm_client):
        super().__init__(llm_client)
        self._context: Dict[str, Any] = {}
        self._page_contents: Dict[int, ContentSlideSchema] = {}
        self._lock = threading.Lock()

    PROMPT_VERSION = os.getenv("CONTENT_AGENT_PROMPT_VERSION", "v2")

    @property
    def system_prompt(self) -> str:
        return load_prompt("content_agent", self.PROMPT_VERSION)

    @property
    def _is_v2(self) -> bool:
        return self.PROMPT_VERSION != "v1"

    # ------------------------------------------------------------------
    # 主执行入口（完全覆盖基类 run，不进 ReAct 循环）
    # ------------------------------------------------------------------

    def run(self, context: Dict[str, Any]) -> Dict:
        self._context = context
        self._page_contents = {}

        outline = context.get("outline", {})
        all_slides = outline.get("items", outline.get("slides", []))

        if not all_slides:
            raise ValueError("大纲为空，无法生成内容")

        shared = self._build_shared_context(context)

        # Structural slides bypass LLM — pre-populate with empty content
        _STRUCTURAL_TYPES = {"title", "agenda", "section_divider"}
        for slide in all_slides:
            if slide.get("slide_type") in _STRUCTURAL_TYPES:
                pn = slide.get("page_number", 0)
                minimal_blocks = [
                    {"type": "heading", "text": slide.get("title", slide.get("takeaway_message", ""))},
                    {"type": "bullet", "text": "", "level": 0},
                    {"type": "bullet", "text": "", "level": 0},
                    {"type": "bullet", "text": "", "level": 0},
                ]
                self._page_contents[pn] = ContentSlideSchema(
                    page_number=pn,
                    slide_type=slide.get("slide_type", "content"),
                    primary_visual=PrimaryVisualType.TEXT_ONLY,
                    text_blocks=minimal_blocks,
                )

        llm_slide_count = sum(1 for s in all_slides if s.get("slide_type") not in _STRUCTURAL_TYPES)
        logger.info(
            f"[ContentAgent] per-slide并行，共{len(all_slides)}页（{llm_slide_count}页需LLM），最多{self.MAX_CONCURRENT}并发"
        )

        report = context.get("report_progress", lambda p, m: None)
        total_slides = llm_slide_count
        completed_count = 0

        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT) as executor:
            futures: Dict = {}
            for i, slide in enumerate(all_slides):
                if slide.get("slide_type") in _STRUCTURAL_TYPES:
                    continue
                prev_slide = all_slides[i - 1] if i > 0 else None
                next_slide = all_slides[i + 1] if i < len(all_slides) - 1 else None
                futures[executor.submit(self._generate_one_slide, slide, prev_slide, next_slide, shared)] = slide

            for fut in as_completed(futures):
                slide = futures[fut]
                pn = slide.get("page_number", "?")
                try:
                    result = fut.result()
                    if result:
                        with self._lock:
                            self._page_contents[result.page_number] = result
                            completed_count += 1
                        pct = 50 + int(completed_count / max(total_slides, 1) * 19)
                        report(pct, f"内容填充: 第{pn}页完成 ({completed_count}/{total_slides})")
                    else:
                        logger.warning(f"[ContentAgent] P{pn} 解析失败，使用占位内容")
                        with self._lock:
                            self._page_contents[pn] = self._make_placeholder(slide)
                            completed_count += 1
                        report(50 + int(completed_count / max(total_slides, 1) * 19),
                               f"内容填充: 第{pn}页（占位） ({completed_count}/{total_slides})")
                except Exception as e:
                    logger.warning(f"[ContentAgent] P{pn} 异常: {e}，使用占位内容")
                    with self._lock:
                        self._page_contents[pn] = self._make_placeholder(slide)
                        completed_count += 1
                    report(50 + int(completed_count / max(total_slides, 1) * 19),
                           f"内容填充: 第{pn}页（失败） ({completed_count}/{total_slides})")

        if not self._page_contents:
            raise ValueError("内容填充失败：所有页面均未生成内容")

        result = self._build_content_result()

        # Chart table routing stats
        total_slides_with_tables = sum(1 for s in all_slides if s.get("primary_visual") == "chart")
        slides_with_chart_data = sum(
            1 for s in result.get("slides", [])
            if s.get("chart_suggestion") and s.get("chart_suggestion") is not None
        )
        logger.info(
            "[ChartTable] 路由统计: chart_pages=%d, chart_filled=%d, total=%d",
            total_slides_with_tables, slides_with_chart_data, len(result.get("slides", [])),
        )

        # Visual block fill rate by layout_hint
        from collections import Counter
        lh_total = Counter()
        lh_vblock_filled = Counter()
        for s in all_slides:
            lh = s.get("layout_hint", "")
            if lh:
                lh_total[lh] += 1
        for s in result.get("slides", []):
            lh = s.get("layout_hint", "")
            if lh and s.get("visual_block"):
                lh_vblock_filled[lh] += 1
        for lh in lh_total:
            logger.info(
                "[VBlockFill] layout_hint=%s: vblock_filled=%d/%d (%.0f%%)",
                lh, lh_vblock_filled.get(lh, 0), lh_total[lh],
                100 * lh_vblock_filled.get(lh, 0) / lh_total[lh] if lh_total[lh] else 0,
            )

        # 2-pass chart dedup: rerun duplicate pages with charts forbidden
        dupes = self._dedupe_charts(result)
        if dupes:
            logger.info(f"[ChartDedup] 检测到{len(dupes)}页重复图表，开始重跑: {dupes}")
            dupe_slides_by_pn = {s["page_number"]: s for s in all_slides if s.get("page_number") in dupes}
            for pn in dupes:
                slide = dupe_slides_by_pn.get(pn)
                if not slide:
                    continue
                idx = next((i for i, s in enumerate(all_slides) if s.get("page_number") == pn), None)
                if idx is None:
                    continue
                prev_s = all_slides[idx - 1] if idx > 0 else None
                next_s = all_slides[idx + 1] if idx < len(all_slides) - 1 else None
                # Tag slide to forbid charts in _build_slide_messages
                slide["_forbid_charts"] = True
                try:
                    rerun_result = self._generate_one_slide(slide, prev_s, next_s, shared)
                    if rerun_result:
                        with self._lock:
                            self._page_contents[rerun_result.page_number] = rerun_result
                        logger.info(f"[ChartDedup] P{pn} 重跑成功")
                    else:
                        logger.warning(f"[ChartDedup] P{pn} 重跑失败，保留原内容但清除图表")
                        with self._lock:
                            existing = self._page_contents.get(pn)
                            if existing:
                                self._page_contents[pn] = existing.model_copy(
                                    update={"chart_suggestion": None, "primary_visual": PrimaryVisualType.TEXT_ONLY}
                                )
                except Exception as e:
                    logger.error(f"[ChartDedup] P{pn} 重跑异常: {e}")
                finally:
                    slide.pop("_forbid_charts", None)

            # Rebuild result after dedup rerun
            result = self._build_content_result()
            logger.info(f"[ChartDedup] 重跑完成，最终chart数=%d", sum(1 for s in result.get("slides", []) if s.get("chart_suggestion")))

        validation = self.validate(result)
        if not validation.valid:
            logger.warning(f"[ContentAgent] 验证警告: {validation.errors}")

        return result

    # ------------------------------------------------------------------
    # 共享上下文（一次性预计算，多线程只读）
    # ------------------------------------------------------------------

    def _build_shared_context(self, context: Dict[str, Any]) -> Dict:
        task = context.get("task", {})
        raw = context.get("raw_content", {})
        outline = context.get("outline", {})
        slides = outline.get("items", outline.get("slides", []))
        source_pages = raw.get("source_pages", [])
        tables = raw.get("_tables", [])

        # 表格清单摘要
        tables_text = ""
        if tables:
            lines = []
            for i, t in enumerate(tables[:6]):
                headers = t.get("headers", [])
                rows = t.get("rows", [])
                sample = " | ".join(str(c) for c in (rows[0] if rows else [])[:6])
                lines.append(
                    f"  表格{i}: {t.get('source_sheet', '表格')} ({len(rows)}行) "
                    f"| 字段: {', '.join(str(h) for h in headers[:6])}"
                    f"\n    首行: {sample}"
                )
            tables_text = "\n".join(lines)

        # 技能指导（一次性加载，注入所有页面）
        skill_section = ""
        try:
            import pipeline.skills.charts        # noqa: F401
            import pipeline.skills.diagrams      # noqa: F401
            import pipeline.skills.visual_blocks  # noqa: F401
            from pipeline.skills import SkillRegistry
            registry = SkillRegistry.get()

            has_chart   = any(s.get("primary_visual") == "chart"   for s in slides)
            has_diagram = any(s.get("primary_visual") == "diagram" for s in slides)
            has_tables  = bool(raw.get("_tables"))

            parts = []
            if has_chart or has_tables:
                g = registry.get_prompt_fragments("chart")
                if g:
                    parts.append(f"### 可用图表类型（chart_suggestion.chart_type）\n{g}")
            if has_diagram:
                g = registry.get_prompt_fragments("diagram")
                if g:
                    parts.append(f"### 可用图示类型（diagram_spec.diagram_type）\n{g}")
            g = registry.get_prompt_fragments("visual_block")
            if g:
                parts.append(f"### 可用视觉块类型（visual_block.type）\n{g}")
            if parts:
                skill_section = "\n## 可用视觉类型（必须使用以下合法值）\n\n" + "\n\n".join(parts) + "\n"
        except Exception as _e:
            logger.debug(f"[ContentAgent] SkillRegistry 加载失败（非致命）: {_e}")

        # 始终准备 raw_text fallback（关键词匹配全部失败时的最后保底）
        raw_text_fallback = (raw.get("_raw_text", "") or "")[:6000]

        # chunks：来自 analyze 阶段，带 id 字段，供 chunk_ids 精确查找
        analysis = context.get("analysis", {})
        chunks = analysis.get("chunks", [])

        # 全局叙事上下文（从 PlanAgent outline 提取）
        narrative_ctx = ""
        scqa = outline.get("scqa")
        if scqa and isinstance(scqa, dict):
            parts = [f"  {k}: {v}" for k, v in scqa.items() if v]
            if parts:
                narrative_ctx += "\n## 叙事框架\n" + "\n".join(parts) + "\n"

        # 全局分析上下文（从 AnalyzeAgent strategy 提取）
        strategy = analysis.get("strategy", {})
        if strategy.get("core_themes"):
            narrative_ctx += (
                "\n## 核心主题\n"
                + "\n".join(f"  - {t}" for t in strategy["core_themes"][:7])
                + "\n"
            )
        if strategy.get("key_messages"):
            narrative_ctx += (
                "\n## 关键信息\n"
                + "\n".join(f"  - {m}" for m in strategy["key_messages"][:5])
                + "\n"
            )

        # 受众分析（v2 only, truncated to 80 chars to control token cost）
        audience_ctx = ""
        if self._is_v2:
            audience_analysis = strategy.get("audience_analysis", "")
            if audience_analysis:
                audience_ctx = f"\n## 受众分析\n  {audience_analysis[:80]}\n"

        # 预计算指标（AnalyzeAgent 产出但从未消费的真实数据）
        metrics_text = ""
        derived = analysis.get("derived_metrics", [])
        if derived:
            lines = []
            for m in derived[:15]:
                name = m.get("name", "")
                val = m.get("formatted_value", m.get("value", ""))
                src = m.get("source_table", "")
                if name and val:
                    lines.append(f"  {name}: {val}" + (f"（来源: {src}）" if src else ""))
            if lines:
                metrics_text = "\n## 已验证的真实数据指标（可直接引用，禁止编造类似数字）\n" + "\n".join(lines) + "\n"

        if narrative_ctx or metrics_text or audience_ctx:
            logger.info(
                f"[ContentAgent] 注入全局叙事上下文: "
                f"scqa={'yes' if scqa else 'no'}, "
                f"themes={len(strategy.get('core_themes', []))}, "
                f"messages={len(strategy.get('key_messages', []))}, "
                f"derived_metrics={len(derived)}, "
                f"audience_analysis={'yes' if audience_ctx else 'no'}"
            )

        return {
            "task": task,
            "source_pages": source_pages,
            "tables": tables,
            "tables_text": tables_text,
            "skill_section": skill_section,
            "raw_text_fallback": raw_text_fallback,
            "chunks": chunks,
            "narrative_ctx": narrative_ctx,
            "metrics_text": metrics_text,
            "audience_ctx": audience_ctx,
        }

    # ------------------------------------------------------------------
    # 单页生成（线程安全，无共享状态写入）
    # ------------------------------------------------------------------

    # Layout_hint → template-specific output guidance
    _TEMPLATE_CONTENT_GUIDE = {
        "narrative": (
            "本页将使用时间线布局。必须填写 visual_block（type=step_cards），每个 item 含 {label, title, description}。\n"
            "text_blocks 仅保留 1-2 条趋势总结/关键洞察，不要逐阶段重复 visual_block 内容。"
        ),
        "metrics": (
            "本页将使用指标卡片布局。必须填写 visual_block（type=kpi_cards），每个 item 含 {title, value, description}。\n"
            "text_blocks 仅保留 1-2 条数据解读，不要重复指标值本身。"
        ),
        "framework_grid": (
            "本页将使用象限/网格布局。必须填写 visual_block（type=icon_text_grid），每个 item 含 {title, description}。\n"
            "text_blocks 仅保留 1 条总结。"
        ),
        "comparison": (
            "本页使用双栏对比布局。建议填写 visual_block（type=comparison_columns），每个 item 含 {title, content}。\n"
            "text_blocks 可保留 1-2 条对比结论，但不要与 visual_block 内容重复。"
        ),
        "chart_focus": (
            "本页以图表为主。chart_suggestion 必须填写。text_blocks 提供 3-5 条图表解读/标注。"
        ),
        "quote_emphasis": (
            "本页强调单一核心结论。第1条 text_block 为核心结论（不超过60字），后续 2-4 条为支撑论据。"
        ),
        "parallel_points": (
            "本页使用并列论据布局。text_blocks 应包含 4-6 条独立并列的论据，每条一句话。不需要 visual_block。"
        ),
        "call_to_action": (
            "结尾行动号召页。生成 1 个核心结论(takeaway_message, 15-40字) "
            "+ text_blocks 中 1-3 个具体行动项(level=1, 每项≤20字)。"
            "不要写长段落，只写可执行的行动步骤。"
        ),
        "tech_architecture": (
            "技术架构图布局。必须填写 visual_block（type=icon_text_grid），"
            "每个 item.title 为层级名（如'应用层'），item.items 为该层组件列表。"
            "2-7 层，每层 2-8 个组件。text_blocks 仅 1 条总结。"
        ),
        "capability_matrix": (
            "能力矩阵布局。必须填写 visual_block（type=icon_text_grid），"
            "每个 item.title 为维度名，item.items 为各列状态（yes/no/partial/planned）。"
            "横轴 2-5 列，纵轴 2-8 行。text_blocks 仅 1 条总结。"
        ),
        "case_study": (
            "客户案例卡布局。visual_block.items[0].title 为客户名，"
            "后续 items 为 KPI（label + value + unit）。text_blocks 前 2 条分别为挑战和方案。"
            "至少 2 个 KPI 大数字。"
        ),
        "solution_comparison": (
            "方案对比布局。visual_block.items 每个 item.title 为评估维度，"
            "item.items 为各方案的评分（best/good/average/poor）+ 备注。"
            "2-4 个方案，3-8 个评估维度。text_blocks 仅 1 条推荐结论。"
        ),
        "end_to_end_flow": (
            "端到端流程布局。必须填写 visual_block（type=step_cards），"
            "每个 item 含 name(阶段名)、actor(执行者)、action(动作)、output(产出)。"
            "4-7 个阶段，箭头自动连接。text_blocks 仅 1 条流程总结。"
        ),
        "image_text_grid": (
            "图文卡片网格布局。必须填写 visual_block（type=image_text_grid），"
            "每个 item 含 {title, description, image_caption}。3-4 张卡片，"
            "image_caption 描述图片内容（如'系统架构图'、'部署拓扑'）。"
            "text_blocks 仅 1 条总结。"
        ),
    }

    @staticmethod
    def _weight_guide(slide: Dict) -> str:
        w = slide.get("page_weight", "pillar")
        if w == "hero":
            return (
                "\n⚠️ 这是全篇核心论点页（hero）。\n"
                "text_blocks 至少4条（1 heading + 3 bullet），每条含具体数据支撑核心论点。\n"
                "必须填写 visual_block（type=stat_highlight），包含一个震撼数字。\n"
                "示例：{\"type\":\"stat_highlight\",\"items\":[{\"title\":\"市场规模\",\"value\":\"1254亿元\",\"description\":\"2024年六大行金融科技投入合计\"}]}"
            )
        elif w == "transition":
            return "\n这是过渡页。text_blocks 最多2条，极简。不需要chart/diagram/visual_block。"
        elif w == "evidence":
            return "\n这是数据展示页。可以信息密集，但必须指定一个primary_metric，其他数字的视觉权重显著低于它。"
        return ""

    def _build_slide_messages(
        self, slide: Dict, prev_slide: Optional[Dict], next_slide: Optional[Dict], shared: Dict
    ) -> List[ChatMessage]:
        """为单个页面构建 LLM 消息（无状态，可多线程并发调用）。"""
        pn = slide.get("page_number", "?")
        st = slide.get("slide_type", "content")
        takeaway = slide.get("takeaway_message", slide.get("takeaway", ""))
        pv = slide.get("primary_visual", "text")
        title = slide.get("title", (takeaway[:20] if takeaway else ""))
        task = shared["task"]

        # 上一页叙事接续（防止内容重复）
        prev_ctx = ""
        if prev_slide:
            prev_title = prev_slide.get("title", "")
            prev_kw = prev_slide.get("takeaway_message", prev_slide.get("takeaway", ""))
            prev_ctx = (
                f"\n## 上一页（叙事接续参考，勿重复）\n"
                f"P{prev_slide.get('page_number')}: {prev_title} | {prev_kw}\n"
            )

        # 下一页叙事预告（v2 only）
        # TODO: Future risk — if user edits takeaway at checkpoint 1, this becomes stale
        next_ctx = ""
        if next_slide and self._is_v2:
            next_kw = next_slide.get("takeaway_message", next_slide.get("takeaway", ""))
            if next_kw:
                next_ctx = (
                    f"\n## 下一页预告（本页结论应自然引出）\n"
                    f"P{next_slide.get('page_number')}: {next_kw}\n"
                )

        # 材料注入：chart 页优先注入表格；非 chart 页在数据相关时也注入
        material_text = ""
        table_injected = False

        # R31: Check for table-type chunks bound to this slide
        table_chunk_prebuilt = self._prebuilt_chart_from_table_chunks(slide, shared)
        if table_chunk_prebuilt:
            material_text = (
                f"\n## 直接可用的 chart_suggestion（从源文档表格生成，100%真实数据）\n"
                f"```json\n{json.dumps(table_chunk_prebuilt, ensure_ascii=False, indent=2)}\n```\n"
                f"请直接使用上述 chart_suggestion 作为你的输出。你可以补充 so_what 注释字段，"
                f"但 categories、series.values 必须原样保留，禁止修改任何数字。\n"
            )
            table_injected = True
        elif shared["tables"]:
            chart_data = self._find_chart_table(slide, shared["tables"])
            if chart_data:
                material_text = f"\n## 数据表格（直接使用，禁止编造数字）\n{chart_data}\n"
                table_injected = True
        if not material_text:
            section_text = self._get_slide_context(slide, shared)
            if section_text:
                material_text = f"\n## 相关原文材料\n{section_text}\n"
            elif shared.get("raw_text_fallback"):
                material_text = f"\n## 原文材料（节选）\n{shared['raw_text_fallback']}\n"

        # R26: Explicit chunk text injection with source binding
        chunks_source = self._resolve_chunks_source(slide, shared)
        if chunks_source:
            material_text += (
                f"\n\n## 本页绑定的源文档原文（所有数据必须来自此处）\n"
                f"{chunks_source}\n"
                f"要求：所有数据、案例、引用必须来自上述原文，不允许编造不存在的数字或案例。"
            )

        # 视觉要求
        has_table_data = bool(table_injected)
        if slide.get("_forbid_charts"):
            visual_req = (
                "本页 chart_suggestion 必须为 null。\n"
                "为补偿失去的图表区域，text_blocks 必须扩展到 4-6 个 bullet，"
                "每个 bullet 长度 30-50 字，需包含具体数字或案例。\n"
                "可选：填写 visual_block（type=kpi_cards）展示关键数据。"
            )
        elif pv == "chart":
            visual_req = (
                "⚠️ chart_suggestion 必须填写（使用上方表格数据，chart_type 使用合法值）"
                if has_table_data
                else (
                    "⚠️ chart_suggestion 必须填写。请从上方原文材料中提炼可量化的数据构建图表。\n"
                    "提炼方法：找出文本中的具体数字（百分比、金额、数量、增长率等），"
                    "组织为 categories（分类/时间）+ series（指标名 + 数值）。\n"
                    "如果原文确实无数值可提炼，chart_suggestion.categories 和 series.values "
                    "可以用定性等级（高/中/低→3/2/1）构建对比图。\n"
                    "禁止编造不存在的数字——只使用原文明确提及的数据。"
                )
            )
        elif has_table_data:
            visual_req = (
                "上游已标记本页为 text_only，但下方注入了相关数据表格——上游可能漏判了图表机会。\n"
                "请你判断：表格数据是否包含明确的对比/趋势/占比关系？\n"
                "- 如果是：填写 chart_suggestion（chart_type 使用合法值）\n"
                "- 如果否（数据是参考性的，不是论点支撑）：设为 null"
            )
        elif pv == "diagram":
            visual_req = "⚠️ diagram_spec 必须填写（diagram_type 使用合法值）"
        elif pv == "visual_block":
            visual_req = "⚠️ visual_block 必须填写（type 使用合法值）"
        else:
            visual_req = "chart_suggestion、diagram_spec、visual_block 均设为 null"

        # Template-specific content structure guidance (overrides generic visual_req)
        from models.template_capacity import LAYOUT_CAPACITIES, DEFAULT_LAYOUT
        layout_hint = slide.get("layout_hint", DEFAULT_LAYOUT)
        template_guide = self._TEMPLATE_CONTENT_GUIDE.get(layout_hint)
        if template_guide:
            visual_req = template_guide

        # Layout hint capacity guidance
        cap = LAYOUT_CAPACITIES.get(layout_hint, LAYOUT_CAPACITIES[DEFAULT_LAYOUT])
        layout_guide = (
            f"\n## 显示容量约束（必须遵守）\n"
            f"- 布局: {cap['description']}\n"
            f"- {cap['content_instruction']}\n"
            f"- 严格遵守上述数量和字数限制，超出部分无法显示\n"
        )

        user_msg = f"""请为以下单个PPT页面生成内容。

## 当前页面
- 页码: P{pn} | 类型: {st} | 视觉: {pv}
- 标题: {title}
- 核心观点: {takeaway}
- 叙事角色: {slide.get('narrative_arc', '未指定')}
- 所属章节: {slide.get('section', '未指定')}
- 目标受众: {task.get('target_audience', '管理层')}
{self._weight_guide(slide)}{prev_ctx}{next_ctx}{material_text}{shared.get('narrative_ctx', '')}{shared.get('metrics_text', '')}{shared.get('audience_ctx', '')}{shared.get('skill_section', '')}{layout_guide}---
{visual_req}
bullet 内容必须来自原文材料，禁止编造。bullet 数量按 page_weight 策略执行（见系统提示）。

请直接输出 JSON 对象，放在 ```json ... ``` 代码块中。"""

        return [ChatMessage(role="user", content=user_msg)]

    def _generate_one_slide(
        self, slide: Dict, prev_slide: Optional[Dict], next_slide: Optional[Dict],
        shared: Dict, user_feedback: str = ""
    ) -> Optional[ContentSlideSchema]:
        """调用 LLM 生成单页内容，含截断检测和重试。线程安全（无写共享状态）。"""
        pn = slide.get("page_number", "?")
        messages = [
            ChatMessage(role="system", content=self.system_prompt),
            *self._build_slide_messages(slide, prev_slide, next_slide, shared),
        ]

        if user_feedback:
            messages.append(ChatMessage(
                role="user",
                content=(
                    f"用户对上一版本的反馈：{user_feedback}\n"
                    "请根据反馈改进，并在输出 JSON 中额外包含 revision_notes 字段，"
                    "用一句话说明做了哪些改动。"
                ),
            ))

        last_parse: Optional[ParseResult] = None
        chunk_text = self._get_slide_context(slide, shared)

        for attempt in range(3):
            try:
                response = self.llm.chat(
                    messages=messages,
                    tools=None,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                if not response.success:
                    raise RuntimeError(f"LLM调用失败: {response.error}")

                # finish_reason 截断检测
                if response.finish_reason in ("length", "max_tokens") and attempt == 0:
                    logger.warning(f"[ContentAgent] P{pn} 输出截断，要求重新输出...")
                    messages.append(ChatMessage(role="assistant", content=response.content or ""))
                    messages.append(ChatMessage(
                        role="user",
                        content="你的输出被截断了，请重新输出完整的JSON对象，减少text_blocks数量确保输出完整。",
                    ))
                    continue

                last_parse = parse_slide(
                    response.content or "", pn,
                    context={"raw_text": chunk_text, "tolerance": 0.05},
                )

                if last_parse.error_kind == "ok":
                    return last_parse.schema

                # Construct retry message based on error type
                if attempt < 2:
                    if last_parse.error_kind == "json_parse":
                        messages.append(ChatMessage(role="assistant", content=response.content or ""))
                        messages.append(ChatMessage(
                            role="user",
                            content="请重新输出JSON对象，确保放在 ```json ... ``` 代码块中，格式正确。",
                        ))
                    elif last_parse.error_kind == "schema":
                        err_msg = last_parse.error_msg
                        if "traceability" in err_msg.lower():
                            messages.append(ChatMessage(role="assistant",
                                content=json.dumps(last_parse.raw_data, ensure_ascii=False)))
                            messages.append(ChatMessage(role="user",
                                content=f"图表数据无法从源文档找到对应数字：{err_msg}\n"
                                        "修复方式（二选一）：\n"
                                        "1. 使用源文档的原始数字（series.values 和 so_what 中的百分比/金额必须能在上方材料中找到）\n"
                                        "2. 在 chart_suggestion 中加 \"estimated\": true，并将 so_what 改写为\"基于行业平均估算\""))
                        else:
                            messages.append(ChatMessage(role="assistant",
                                content=json.dumps(last_parse.raw_data, ensure_ascii=False)))
                            messages.append(ChatMessage(role="user",
                                content=f"输出违反schema规则：{err_msg}\n"
                                        "修复要求：1) 只有一种visual字段 2) chart必须有series/data 3) visual_block必须有type和非空items"))
                    continue

            except Exception as e:
                if attempt < 2:
                    logger.warning(f"[ContentAgent] P{pn} 第{attempt+1}次失败({e})，重试...")
                    continue
                logger.error(f"[ContentAgent] P{pn} 最终失败: {e}")

        # === Unified final-fail handling ===
        self._record_degradation(pn, f"all retries exhausted: {last_parse.error_kind if last_parse else 'exception'}")

        if last_parse and last_parse.error_kind == "schema" and last_parse.raw_data:
            # LLM produced text but visual schema violated → keep text, clear visuals
            return degrade_to_text_only(last_parse.raw_data)
        else:
            # LLM produced nothing (json_parse all failed / exception) → placeholder
            return make_placeholder(
                page_number=pn,
                slide_type=slide.get("slide_type", "content"),
                title=slide.get("title", ""),
                takeaway=slide.get("takeaway_message", ""),
            )

    # ------------------------------------------------------------------
    # 材料匹配（静态，线程安全）
    # ------------------------------------------------------------------

    @staticmethod
    def _prebuilt_chart_from_table_chunks(slide: Dict, shared: Dict) -> Optional[Dict]:
        """R31: Build chart_suggestion directly from table-type chunks bound to this slide.
        Returns None if no table chunks or primary_visual is not chart."""
        if slide.get("primary_visual") != "chart":
            return None
        bound_ids = set(slide.get("chunk_ids", []))
        if not bound_ids:
            return None
        chunks = shared.get("chunks", [])
        table_chunks = [c for c in chunks if c.get("id") in bound_ids and c.get("type") == "table"]
        if not table_chunks:
            return None
        tc = table_chunks[0]
        table_data = tc.get("table_data")
        if not table_data or not table_data.get("headers") or not table_data.get("rows"):
            return None
        headers = table_data["headers"]
        rows = table_data["rows"]
        if len(headers) < 2 or not rows:
            return None

        # Build chart spec from table
        import re
        def _parse_num(v):
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip().replace(",", "").replace("%", "").replace("亿", "e8").replace("万", "e4")
            try:
                return float(re.sub(r"[^\d.\-eE]", "", s))
            except (ValueError, TypeError):
                return None

        categories = [str(r[0])[:20] for r in rows if r]
        series_list = []
        for col_idx in range(1, len(headers)):
            name = str(headers[col_idx])[:20]
            values = []
            for r in rows:
                if col_idx < len(r):
                    values.append(_parse_num(r[col_idx]))
                else:
                    values.append(None)
            if any(v is not None for v in values):
                series_list.append({"name": name, "values": values})

        if not series_list or not categories:
            return None

        chart_type = "column" if len(categories) <= 8 else "line"
        return {
            "chart_type": chart_type,
            "categories": categories,
            "series": series_list,
            "source_table_id": tc.get("id", ""),
        }

    @staticmethod
    def _resolve_chunks_source(slide: Dict, shared: Dict) -> str:
        """R26: Resolve bound chunks into explicit source text for LLM prompt."""
        bound_ids = set(slide.get("chunk_ids", []))
        if not bound_ids:
            return ""
        chunks = shared.get("chunks", [])
        relevant = [c for c in chunks if c.get("id") in bound_ids]
        if not relevant:
            return ""
        parts = []
        for c in relevant:
            cid = c.get("id", "")
            text = c.get("text", "")
            ctype = c.get("type", "text")
            section = c.get("section", "")
            header = f"[{ctype} chunk {cid}"
            if section:
                header += f" · {section}"
            header += "]"
            parts.append(f"{header}\n{text}")
        return "\n\n".join(parts)

    @staticmethod
    def _get_slide_context(slide: Dict, shared: Dict) -> str:
        """精确 chunk_ids 查找，降级到 bigram 关键词搜索。"""
        bound_ids = set(slide.get("chunk_ids", []))
        if bound_ids:
            relevant = [c for c in shared.get("chunks", []) if c.get("id") in bound_ids]
            if relevant:
                return "\n\n".join(c.get("text", c.get("content", "")) for c in relevant[:5])
        # 降级：bigram 搜索
        return ContentAgent._find_best_section(slide, shared["source_pages"])

    @staticmethod
    def _extract_kw(text: str) -> List[str]:
        """English word tokens + Chinese bigrams — works without jieba."""
        import re
        words: List[str] = []
        for segment in re.split(r'[\s\W]+', text.lower()):
            if not segment or len(segment) < 2:
                continue
            if all('一' <= c <= '鿿' for c in segment):
                # Chinese: emit overlapping bigrams for fuzzy matching
                words.extend(segment[i:i + 2] for i in range(len(segment) - 1))
            else:
                words.append(segment)
        return words

    @staticmethod
    def _find_best_section(slide: Dict, source_pages: List[Dict]) -> str:
        """关键词匹配原文章节，top-2 动态阈值：最相关必返回，次相关需达最高分60%。"""
        if not source_pages:
            return ""
        title = slide.get("title", "")
        takeaway = slide.get("takeaway_message", slide.get("takeaway", ""))
        section = slide.get("section", "")
        hint = slide.get("supporting_hint", "")

        # Fast-path: supporting_hint 精确匹配章节标题
        if hint:
            for sp in source_pages:
                if (sp.get("title") or "").strip() == hint.strip():
                    return sp.get("content", "")[:3000]

        kw_list = ContentAgent._extract_kw(f"{title} {section} {takeaway} {hint}")
        if not kw_list:
            return ""

        scored = []
        for sp in source_pages:
            t = (sp.get("title") or "").lower()
            c = (sp.get("content") or "").lower()
            score = sum(3 if w in t else (1 if w in c else 0) for w in kw_list)
            if score > 0:
                scored.append((score, sp))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]
        threshold = best_score * 0.6

        parts = [best.get("content", "")[:3000]]
        if len(scored) > 1 and scored[1][0] >= threshold:
            parts.append(scored[1][1].get("content", "")[:1500])

        return "\n---\n".join(parts)

    @staticmethod
    def _find_chart_table(slide: Dict, tables: List[Dict]) -> str:
        """为 chart 页匹配最相关表格，top-2 注入：最相关20行，次相关5行摘要。"""
        if not tables:
            return ""
        title = slide.get("title", "")
        takeaway = slide.get("takeaway_message", slide.get("takeaway", ""))
        data_source = slide.get("data_source", "")
        kw_list = ContentAgent._extract_kw(f"{title} {takeaway} {data_source}")

        scored = []
        for i, t in enumerate(tables):
            headers_str = " ".join(str(h) for h in t.get("headers", [])).lower()
            sheet_str = (t.get("source_sheet", "")).lower()
            score = sum(1 for w in kw_list if w in headers_str or w in sheet_str)
            scored.append((score, i, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_idx, t1 = scored[0]

        if best_score == 0:
            logger.info(
                f"[ChartTable] 无关键词匹配，跳过表格注入 | slide={slide.get('page_number')} "
                f"data_source={data_source!r} title={title!r}"
            )
            return ""

        logger.debug(
            f"[ChartTable] 匹配成功 | slide={slide.get('page_number')} "
            f"score={best_score} tables={len(tables)} best_idx={best_idx}"
        )

        result_parts = []

        _, _, t1 = scored[0]  # best_idx, t1 already unpacked above
        headers1 = t1.get("headers", [])
        rows1 = t1.get("rows", [])
        lines = [f"📊 主表格「{t1.get('source_sheet', '')}」({len(rows1)}行，直接使用以下数字，禁止编造):"]
        lines.append("| " + " | ".join(str(h) for h in headers1[:8]) + " |")
        for row in rows1[:20]:
            lines.append("| " + " | ".join(str(c) for c in row[:8]) + " |")
        if len(rows1) > 20:
            lines.append(f"（共{len(rows1)}行，已截断）")
        result_parts.append("\n".join(lines))

        if len(scored) > 1 and scored[0][0] > 0 and scored[1][0] >= scored[0][0] * 0.6:
            _, _, t2 = scored[1]
            if t2 is not t1:
                headers2 = t2.get("headers", [])
                rows2 = t2.get("rows", [])
                lines2 = [
                    f"📊 参考表格「{t2.get('source_sheet', '')}」"
                    f"({len(rows2)}行，字段: {', '.join(str(h) for h in headers2[:6])}):"
                ]
                for row in rows2[:5]:
                    lines2.append("  " + " | ".join(str(c) for c in row[:6]))
                result_parts.append("\n".join(lines2))

        return "\n\n".join(result_parts)

    # ------------------------------------------------------------------
    # 解析与组装
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_single_page(text: str, page_number: int) -> ParseResult:
        """从 LLM 输出中提取单个 JSON 对象，返回 tagged ParseResult。"""
        return parse_slide(text, page_number)

    @staticmethod
    def _parse_pages_from_text(text: str) -> list:
        """从文本中提取 JSON 数组（extract_output 兼容接口）。"""
        import re
        for pattern in [r'```json\s*(\[[\s\S]*?\])\s*```', r'```\s*(\[[\s\S]*?\])\s*```']:
            for match in re.finditer(pattern, text, re.DOTALL):
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        if "page_number" in data[0] or "text_blocks" in data[0]:
                            return data
                except Exception:
                    continue
        return []

    @staticmethod
    def _make_placeholder(slide: Dict) -> ContentSlideSchema:
        """为失败页面生成占位内容（is_failed=True）。"""
        return make_placeholder(
            page_number=slide.get("page_number", 0),
            slide_type=slide.get("slide_type", "content"),
            title=slide.get("title", ""),
            takeaway=slide.get("takeaway_message", slide.get("takeaway", "")),
        )

    def _record_degradation(self, page_number, reason: str):
        """Record a degradation event for diagnostics."""
        logger.warning("[ContentAgent] P%s degraded: %s", page_number, reason)

    def _dedupe_charts(self, result: Dict) -> List[int]:
        """Detect duplicate chart_suggestion signatures across slides."""
        seen: Dict = {}
        dupes: List[int] = []
        for s in result.get("slides", []):
            chart = s.get("chart_suggestion")
            if not chart or not isinstance(chart, dict):
                continue
            try:
                sig = (chart.get("chart_type", ""),
                       tuple(round(v, 1) for v in chart.get("series", [{}])[0].get("values", [])))
            except (IndexError, TypeError, ValueError):
                continue
            pn = s.get("page_number")
            if sig in seen:
                dupes.append(pn)
                logger.info(f"[ChartDedup] 重复图表 P{pn} 与 P{seen[sig]}: type={sig[0]} values={sig[1]}")
            else:
                seen[sig] = pn
        return dupes

    def _build_content_result(self) -> Dict:
        """将收集的页面内容组装为 ContentResultSchema，边界 dump 成 dict。"""
        outline = self._context.get("outline", {})
        outline_slides = {
            s["page_number"]: s
            for s in outline.get("items", outline.get("slides", []))
        }

        _STRUCTURAL_TYPES = {"title", "agenda", "section_divider"}
        slides: list[ContentSlideSchema] = []
        for pn in sorted(self._page_contents.keys()):
            page = self._page_contents[pn]
            outline_page = outline_slides.get(pn, {})
            if outline_page.get("slide_type") in _STRUCTURAL_TYPES:
                continue

            # Normalize text_blocks from schema instance
            raw_blocks = page.text_blocks or []
            text_blocks = []
            for b in raw_blocks:
                if isinstance(b, dict):
                    text_blocks.append({
                        "content": b.get("text", b.get("content", "")),
                        "level": b.get("level", 0),
                        "is_bold": b.get("type") == "heading",
                    })

            takeaway = (
                outline_page.get("takeaway_message")
                or outline_page.get("takeaway")
                or page.takeaway_message
            )

            updated = page.model_copy(update={
                "takeaway_message": takeaway,
                "text_blocks": text_blocks,
                "slide_type": outline_page.get("slide_type", page.slide_type.value if isinstance(page.slide_type, SlideType) else page.slide_type),
                "layout_hint": outline_page.get("layout_hint", page.layout_hint),
                "page_weight": outline_page.get("page_weight", page.page_weight),
                "source_note": page.source_note or "",
            })
            slides.append(updated)

        result = ContentResultSchema(slides=slides)

        # Visual field fill rates
        chart_count = sum(1 for s in result.slides if s.primary_visual == PrimaryVisualType.CHART)
        diagram_count = sum(1 for s in result.slides if s.primary_visual == PrimaryVisualType.DIAGRAM)
        vblock_count = sum(1 for s in result.slides if s.primary_visual == PrimaryVisualType.VISUAL_BLOCK)
        logger.info(
            "CONTENT_VISUAL_RATES total=%d chart=%d diagram=%d visual_block=%d",
            len(slides), chart_count, diagram_count, vblock_count,
        )

        return content_schema_to_dict(result)


    def validate(self, output: Dict) -> ValidationResult:
        errors: list[str] = []
        slides = output.get("slides", [])
        outline = self._context.get("outline", {})
        outline_slides = outline.get("items", outline.get("slides", []))

        if not slides:
            errors.append("内容结果为空")
            return ValidationResult(valid=False, errors=errors)

        if len(slides) < len(outline_slides) * 0.7:
            errors.append(f"内容页数({len(slides)})远少于大纲页数({len(outline_slides)})")

        # Schema-level validation
        for s in slides:
            pn = s.get("page_number", "?")
            text_blocks = s.get("text_blocks", [])
            if not text_blocks:
                errors.append(f"第{pn}页 text_blocks 为空")
                continue
            content_blocks = [b for b in text_blocks if b.get("content", "").strip() and not b.get("is_bold")]
            if len(content_blocks) < 1:
                errors.append(f"第{pn}页内容过少（少于1个正文块）")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    # ------------------------------------------------------------------
    # 工具辅助方法（供调试 / /rerun-page 复用）
    # ------------------------------------------------------------------

    def _tool_read_outline(self) -> str:
        outline = self._context.get("outline", {})
        slides = outline.get("items", outline.get("slides", []))
        lines = [f"=== 大纲（共{len(slides)}页）==="]
        for s in slides:
            pn = s.get("page_number", "?")
            pv = s.get("primary_visual", "text")
            takeaway = s.get("takeaway_message", s.get("takeaway", ""))
            lines.append(
                f"P{pn}: [{s.get('slide_type', '')}] {s.get('title', takeaway[:15])} | "
                f"takeaway: {takeaway} | visual: {pv}"
            )
        return "\n".join(lines)

    def _tool_read_raw_material(self, section: str, max_chars: int = 2000) -> str:
        raw = self._context.get("raw_content", {})
        for sp in raw.get("source_pages", []):
            if section.lower() in (sp.get("title") or "").lower():
                return f"【{sp['title']}】\n{sp.get('content', '')[:max_chars]}"
        text = raw.get("_raw_text", "")
        idx = text.lower().find(section.lower())
        if idx >= 0:
            return text[max(0, idx - 50): idx + max_chars]
        return f"未找到章节 '{section}'"

    def _tool_query_table(self, table_index: int, columns: Optional[List[str]] = None) -> str:
        raw = self._context.get("raw_content", {})
        tables = raw.get("_tables", [])
        if table_index >= len(tables):
            return f"表格{table_index}不存在（共{len(tables)}个）"
        t = tables[table_index]
        headers = t.get("headers", [])
        rows = t.get("rows", [])
        if columns:
            col_indices = [headers.index(c) for c in columns if c in headers]
            selected_headers = [headers[i] for i in col_indices]
            selected_rows = [[row[i] for i in col_indices if i < len(row)] for row in rows]
        else:
            selected_headers = headers
            selected_rows = rows
        lines = [f"表格{table_index}: {t.get('source_sheet', '')}", " | ".join(str(h) for h in selected_headers)]
        for row in selected_rows[:20]:
            lines.append(" | ".join(str(c) for c in row))
        if len(selected_rows) > 20:
            lines.append(f"... 共{len(selected_rows)}行")
        return "\n".join(lines)

    def _tool_read_skill_guidance(self, skill_type: str) -> str:
        try:
            import pipeline.skills.charts        # noqa: F401
            import pipeline.skills.diagrams      # noqa: F401
            import pipeline.skills.visual_blocks  # noqa: F401
            from pipeline.skills import SkillRegistry
            registry = SkillRegistry.get()
            skill = (
                registry.find("chart", skill_type)
                or registry.find("diagram", skill_type)
                or registry.find("visual_block", skill_type)
            )
            if skill:
                return skill.prompt_fragment()
        except Exception:
            pass
        return f"未找到技能 '{skill_type}' 的指导"
