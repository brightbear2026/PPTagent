"""
DEPRECATED: Legacy design agent. Only used when RENDER_MODE != "html" or Node.js is unavailable.
See HTMLDesignAgent for the primary rendering path.

DesignAgent — 混合 CodeAgent + ReActAgent
将 ContentResult + OutlineResult 转换为完整的 PresentationSpec（SlideSpec 列表）。

策略：
1. 代码部分（批量无LLM）：复用现有 _run_design 逻辑 → 生成 SlideSpec 骨架
2. LLM部分（ReAct，可选）：仅对缺失图表的 data 页面补充 chart spec

输出：{"pres_spec": ..., "slide_count": ..., "chart_count": ..., "diagram_count": ...}
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from .base import CodeAgent

logger = logging.getLogger(__name__)


class DesignAgent(CodeAgent):
    """
    视觉设计 Agent。

    主体是纯代码逻辑（复用 _run_design），不进 ReAct 循环。
    未来可选地对缺失图表启用 LLM 辅助生成。
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def run(self, context: Dict[str, Any]) -> Dict:
        from pipeline.layer4_visual import VisualDesigner
        from pipeline.layer5_chart import ChartGenerator
        from models.slide_spec import (
            PresentationSpec, SlideSpec, SlideType, TextBlock,
            NarrativeRole, ContentPattern, VisualTheme,
            ChartSpec, ChartType, ChartSeries,
            DiagramSpec, DiagramNode, DiagramEdge,
            OutlineResult, ContentResult, AnalysisResult, EnrichedTableData,
        )

        task = context.get("task", {})
        outline_data = context.get("outline", {})
        content_data = context.get("content", {})

        if not outline_data or not content_data:
            raise RuntimeError("缺少大纲或内容结果，无法构建PPT")

        outline = OutlineResult.from_dict(outline_data)
        content = ContentResult.from_dict(content_data)

        # 加载 enriched_tables 用于图表数据校验
        enriched_tables: list[EnrichedTableData] = []
        try:
            analysis_data = context.get("analysis", {})
            if analysis_data:
                analysis = AnalysisResult.from_dict(analysis_data)
                enriched_tables = analysis.enriched_tables
        except Exception as e:
            logger.warning(f"[DesignAgent] 加载enriched_tables失败: {e}")

        language = task.get("language", "zh")
        total_pages = len(outline.items)
        content_by_page = {s.page_number: s for s in content.slides}

        # ── 构建 SlideSpec 列表 ──
        slides = []
        skipped_pages = []
        for idx, item in enumerate(outline.items):
            slide = SlideSpec(
                slide_index=item.page_number - 1,
                takeaway_message=item.takeaway_message,
            )

            # slide_type
            try:
                slide.slide_type = SlideType(item.slide_type)
            except ValueError:
                slide.slide_type = SlideType.CONTENT

            # narrative_arc：优先使用 PlanAgent LLM 直接填写的值，回退到关键词推断
            llm_arc = getattr(item, "narrative_arc", "") or ""
            if llm_arc:
                try:
                    slide.narrative_arc = NarrativeRole(llm_arc)
                except ValueError:
                    slide.narrative_arc = self._infer_narrative_arc(
                        item.slide_type,
                        getattr(item, "section", "") or "",
                        item.takeaway_message or "",
                        idx,
                        total_pages,
                    )
            elif idx == 0:
                slide.narrative_arc = NarrativeRole.OPENING
            elif idx == total_pages - 1:
                slide.narrative_arc = NarrativeRole.CLOSING
            else:
                slide.narrative_arc = self._infer_narrative_arc(
                    item.slide_type,
                    getattr(item, "section", "") or "",
                    item.takeaway_message or "",
                    idx,
                    total_pages,
                )

            page_content = content_by_page.get(item.page_number)
            if page_content and getattr(page_content, "is_failed", False):
                reason = getattr(page_content, "error", "content_failed")
                logger.warning(f"[DesignAgent] 跳过失败页面 {item.page_number}: {reason}")
                skipped_pages.append({"page_number": item.page_number, "reason": reason})
                continue

            if page_content:
                slide.text_blocks = page_content.text_blocks
                if not slide.text_blocks:
                    slide.text_blocks = [
                        TextBlock(content=item.takeaway_message, level=0, is_bold=True),
                    ]
                    if getattr(item, "supporting_hint", ""):
                        slide.text_blocks.append(
                            TextBlock(content=item.supporting_hint, level=1)
                        )

                slide.source_note = page_content.source_note

                if page_content.chart_suggestion:
                    slide.charts = self._convert_chart_suggestion(
                        page_content.chart_suggestion, ChartType, ChartSeries, ChartSpec
                    )
                    if slide.charts and enriched_tables:
                        slide.charts = [
                            self._validate_chart(c, enriched_tables)
                            for c in slide.charts
                        ]

                if page_content.diagram_spec:
                    diag = self._convert_diagram_spec(
                        page_content.diagram_spec, DiagramSpec, DiagramNode, DiagramEdge
                    )
                    if diag:
                        slide.diagrams = [diag]

                if getattr(page_content, "visual_block", None):
                    slide.visual_block = page_content.visual_block

                pv = getattr(page_content, "primary_visual", "") or ""
                if not pv:
                    pv = self._infer_primary_visual(page_content)
                slide.primary_visual = pv

                if pv == "chart":
                    slide.diagrams = []
                    slide.visual_block = None
                elif pv == "diagram":
                    slide.charts = []
                    slide.visual_block = None
                elif pv in ("visual_block", "text_only"):
                    slide.charts = []
                    slide.diagrams = []
                    if pv == "text_only":
                        slide.visual_block = None
            else:
                slide.text_blocks = [
                    TextBlock(content=item.takeaway_message, level=0, is_bold=True),
                ]

            slides.append(slide)

        # 图片分发
        try:
            raw_data = context.get("raw_content", {})
            raw_images = raw_data.get("_images", [])
            image_paths = [
                img["file_path"] for img in raw_images
                if isinstance(img, dict) and img.get("file_path") and os.path.exists(img["file_path"])
            ]
            if image_paths:
                self._distribute_pictures(slides, image_paths)
        except Exception as e:
            logger.warning(f"[DesignAgent] 图片分发失败: {e}")

        # Layer 4: 视觉设计
        designer = VisualDesigner()
        slides = designer.design_slides(slides, language=language)

        # Layer 5: LLM 辅助图表补充
        if self.llm:
            for slide in slides:
                if not slide.charts and slide.slide_type in (
                    SlideType.DATA, SlideType.CONTENT
                ) and slide.content_pattern in (
                    ContentPattern.LEFT_CHART_RIGHT_TEXT,
                    ContentPattern.LEFT_TEXT_RIGHT_CHART,
                    ContentPattern.DATA_DASHBOARD,
                ):
                    try:
                        chart_gen = ChartGenerator(self.llm, enriched_tables=enriched_tables)
                        chart = chart_gen._generate_chart(slide)
                        if chart:
                            if enriched_tables:
                                chart = self._validate_chart(chart, enriched_tables)
                            slide.charts.append(chart)
                    except Exception as e:
                        logger.warning(f"[DesignAgent] 图表生成失败 slide {slide.slide_index}: {e}")

        pres_title = task.get("title", "") or "演示文稿"
        pres_spec = PresentationSpec(title=pres_title, slides=slides, language=language)

        result = {
            "pres_spec": pres_spec.to_dict(),
            "slide_count": len(slides),
            "chart_count": sum(len(s.charts) for s in slides),
            "diagram_count": sum(len(s.diagrams) for s in slides),
        }
        if skipped_pages:
            result["skipped_pages"] = skipped_pages
            logger.warning(f"[DesignAgent] {len(skipped_pages)}页被跳过: {[p['page_number'] for p in skipped_pages]}")
        return result

    # ------------------------------------------------------------------
    # 辅助方法（从旧 PipelineController 迁移）
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_narrative_arc(slide_type: str, section: str, takeaway: str, idx: int, total: int):
        """
        基于 slide_type + section/takeaway 关键词推断 narrative_arc。
        匹配顺序：关键词映射 → 位置启发（前1/3→CONTEXT，中1/3→EVIDENCE，后1/3→ANALYSIS）
        """
        from models.slide_spec import NarrativeRole

        text = f"{section} {takeaway}".lower()

        # transition/agenda 类型
        if slide_type in ("transition", "agenda"):
            return NarrativeRole.CONTEXT

        # 关键词映射（Minto Pyramid + SCQA 对应）
        CLOSING_KW = {"结论", "总结", "建议", "行动", "下一步", "展望", "计划"}
        COMPLICATION_KW = {"问题", "挑战", "困难", "风险", "瓶颈", "痛点", "不足"}
        CONTEXT_KW = {"背景", "现状", "概述", "介绍", "情况", "概况", "基础"}
        RESOLUTION_KW = {"方案", "解决", "策略", "路径", "举措", "措施", "方法", "优化"}
        EVIDENCE_KW = {"数据", "分析", "验证", "案例", "对比", "趋势", "指标", "结果"}

        if any(k in text for k in CLOSING_KW):
            return NarrativeRole.CLOSING
        if any(k in text for k in COMPLICATION_KW):
            return NarrativeRole.EVIDENCE   # 问题/挑战作为支撑证据
        if any(k in text for k in CONTEXT_KW):
            return NarrativeRole.CONTEXT
        if any(k in text for k in RESOLUTION_KW):
            return NarrativeRole.CONTEXT    # 方案类靠近上下文
        if any(k in text for k in EVIDENCE_KW) or slide_type in ("data", "diagram"):
            return NarrativeRole.EVIDENCE

        # 位置 fallback：前1/3→CONTEXT，后1/3→EVIDENCE（分析过渡），中间→EVIDENCE
        pos_ratio = idx / max(total - 1, 1)
        if pos_ratio < 0.25:
            return NarrativeRole.CONTEXT
        return NarrativeRole.EVIDENCE

    @staticmethod
    def _convert_chart_suggestion(cs, ChartType, ChartSeries, ChartSpec):
        try:
            chart_type = ChartType(cs.chart_type)
        except ValueError:
            chart_type = ChartType.COLUMN

        # LLM may use "data" or "values" for numeric data; accept both
        series = [
            ChartSeries(
                name=s.get("name", ""),
                values=[float(v) for v in (s.get("values") or s.get("data") or []) if v is not None],
            )
            for s in cs.series
        ]

        # Categories: top-level field takes priority; fallback to first series' "labels"
        categories = cs.categories
        if not categories and cs.series:
            categories = cs.series[0].get("labels", [])

        chart = ChartSpec(
            chart_type=chart_type,
            title=cs.title,
            categories=[str(c) for c in categories],
            series=series,
            so_what=cs.so_what,
            show_legend=len(series) > 1,
            show_data_labels=True,
        )
        return [chart]

    @staticmethod
    def _convert_diagram_spec(cds, DiagramSpec, DiagramNode, DiagramEdge):
        nodes, edges = [], []

        if cds.process_flow:
            pf = cds.process_flow
            for n in pf.nodes:
                nodes.append(DiagramNode(node_id=str(n.get("id", len(nodes)+1)), label=n.get("label", "")))
            for c in pf.connections:
                edges.append(DiagramEdge(from_id=str(c.get("from", "")), to_id=str(c.get("to", "")), label=c.get("label", "")))
            return DiagramSpec(diagram_type="process_flow", nodes=nodes, edges=edges,
                               layout_direction="LR" if pf.direction == "horizontal" else "TB",
                               title=cds.title)

        elif cds.relationship:
            rs = cds.relationship
            for n in rs.nodes:
                nodes.append(DiagramNode(node_id=str(n.get("id", len(nodes)+1)), label=n.get("label", "")))
            for e in rs.edges:
                edges.append(DiagramEdge(from_id=str(e.get("from", "")), to_id=str(e.get("to", "")), label=e.get("label", "")))
            return DiagramSpec(diagram_type="relationship", nodes=nodes, edges=edges, title=cds.title)

        elif cds.architecture:
            arch = cds.architecture
            for layer in arch.layers:
                layer_label = layer.get("label", "")
                for item in layer.get("items", []):
                    label = item if isinstance(item, str) else item.get("label", str(item))
                    nodes.append(DiagramNode(node_id=f"n_{len(nodes)}", label=label, group=layer_label))
            if not nodes and arch.root:
                nodes.append(DiagramNode(node_id="root", label=arch.root.get("label", "")))
            return DiagramSpec(diagram_type="architecture", nodes=nodes, title=cds.title)

        elif cds.framework:
            fw = cds.framework
            if fw.quadrants:
                for q in fw.quadrants:
                    pos = q.get("position", "")
                    for item in q.get("items", []):
                        nodes.append(DiagramNode(node_id=f"n_{len(nodes)}", label=str(item), group=pos))
            elif fw.pyramid_levels:
                for lvl in fw.pyramid_levels:
                    nodes.append(DiagramNode(node_id=f"n_{len(nodes)}", label=lvl.get("label", ""), sublabel=lvl.get("desc", ""), group="default"))
            elif fw.funnel_stages:
                for st in fw.funnel_stages:
                    nodes.append(DiagramNode(node_id=f"n_{len(nodes)}", label=st.get("label", ""), group="default"))
            elif fw.strengths or fw.weaknesses or fw.opportunities or fw.threats:
                for item in fw.strengths:
                    nodes.append(DiagramNode(node_id=f"n_{len(nodes)}", label=str(item), group="top_left"))
                for item in fw.weaknesses:
                    nodes.append(DiagramNode(node_id=f"n_{len(nodes)}", label=str(item), group="top_right"))
                for item in fw.opportunities:
                    nodes.append(DiagramNode(node_id=f"n_{len(nodes)}", label=str(item), group="bottom_left"))
                for item in fw.threats:
                    nodes.append(DiagramNode(node_id=f"n_{len(nodes)}", label=str(item), group="bottom_right"))
            return DiagramSpec(diagram_type="framework", nodes=nodes, title=cds.title)

        return None

    @staticmethod
    def _validate_chart(chart, enriched_tables):
        """尝试用真实表格数据校验图表值（不匹配则保留原值）"""
        try:
            from pipeline.layer5_chart import ChartGenerator
            gen = ChartGenerator(llm=None, enriched_tables=enriched_tables)
            if hasattr(gen, "_validate_and_fix_chart"):
                return gen._validate_and_fix_chart(chart, enriched_tables)
        except Exception:
            pass
        return chart

    @staticmethod
    def _infer_primary_visual(page_content) -> str:
        if page_content.chart_suggestion:
            return "chart"
        if page_content.diagram_spec:
            return "diagram"
        if getattr(page_content, "visual_block", None):
            return "visual_block"
        return "text"

    @staticmethod
    def _distribute_pictures(slides, image_paths):
        from models.slide_spec import SlideType as _ST
        skip = {_ST.TITLE, _ST.AGENDA, _ST.SECTION_DIVIDER, _ST.SUMMARY}
        candidates = [s for s in slides if s.slide_type not in skip and not s.charts and not s.diagrams]
        if not candidates:
            candidates = [s for s in slides if s.slide_type not in skip]
        if not candidates:
            return
        for i, path in enumerate(image_paths):
            candidates[i % len(candidates)].pictures.append(path)
