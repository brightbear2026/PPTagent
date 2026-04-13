"""
Pipeline控制器 — 5阶段 / 2检查点

parse(silent) → analyze(silent) → outline[checkpoint1] → content[checkpoint2] → build(silent)

parse+analyze 静默执行，outline 和 content 是两个检查点。
build 阶段连续执行视觉设计+图表+布局+输出，不暂停。
"""

import asyncio
import json
import os
from typing import Optional, Dict, Any

from storage import get_store, PIPELINE_STAGES
from models.slide_spec import (
    DiagramSpec, DiagramNode, DiagramEdge,
    ChartType, ChartSpec, ChartSeries,
)


# 2个检查点
PAUSE_AFTER_STAGES = {"outline", "content"}

# 阶段 → 进度百分比映射
STAGE_PROGRESS = {
    "parse":    (5, 15, "输入解析"),
    "analyze":  (15, 30, "数据分析"),
    "outline":  (30, 50, "大纲生成"),
    "content":  (50, 75, "内容填充"),
    "build":    (75, 100, "PPT构建"),
}


class PipelineController:
    """
    Pipeline执行控制器

    5个阶段，2个检查点。parse/analyze静默执行，
    outline和content是用户审阅点，build连续完成。
    """

    def __init__(self):
        self.store = get_store()

    async def run_full(self, task_id: str):
        """从第一个pending阶段执行到下一个检查点或完成"""
        self.store.update_task(task_id, status="processing")

        for stage in PIPELINE_STAGES:
            task = self.store.get_task(task_id)
            if not task or task["status"] == "cancelled":
                return

            stage_info = self.store.get_stage(task_id, stage)
            if stage_info and stage_info["status"] == "completed":
                continue

            success = await self._execute_stage(task_id, stage)
            if not success:
                return

            if stage in PAUSE_AFTER_STAGES:
                self.store.update_task(task_id,
                    status="checkpoint",
                    current_stage=stage,
                    current_step=STAGE_PROGRESS[stage][2],
                    message=f"检查点: 请确认{STAGE_PROGRESS[stage][2]}结果")
                return

        self.store.update_task(task_id,
            status="completed",
            progress=100,
            current_step="完成",
            message="PPT生成完成！")

    async def resume_from(self, task_id: str, from_stage: str):
        """从指定阶段恢复执行"""
        self.store.reset_stages_from(task_id, from_stage)
        self.store.update_task(task_id, status="processing")

        from_idx = PIPELINE_STAGES.index(from_stage)
        for stage in PIPELINE_STAGES[from_idx:]:
            task = self.store.get_task(task_id)
            if not task or task["status"] == "cancelled":
                return

            success = await self._execute_stage(task_id, stage)
            if not success:
                return

            if stage in PAUSE_AFTER_STAGES:
                self.store.update_task(task_id,
                    status="checkpoint",
                    current_stage=stage,
                    current_step=STAGE_PROGRESS[stage][2],
                    message=f"检查点: 请确认{STAGE_PROGRESS[stage][2]}结果")
                return

        self.store.update_task(task_id,
            status="completed",
            progress=100,
            current_step="完成",
            message="PPT生成完成！")

    async def confirm_checkpoint(self, task_id: str):
        """用户确认当前检查点，继续执行"""
        task = self.store.get_task(task_id)
        if not task or task["status"] != "checkpoint":
            return

        current = task.get("current_stage", "")
        if not current:
            return

        current_idx = PIPELINE_STAGES.index(current) if current in PIPELINE_STAGES else -1
        next_stages = PIPELINE_STAGES[current_idx + 1:]

        if not next_stages:
            self.store.update_task(task_id, status="completed", progress=100)
            return

        self.store.update_task(task_id, status="processing")

        for stage in next_stages:
            task = self.store.get_task(task_id)
            if not task or task["status"] == "cancelled":
                return

            success = await self._execute_stage(task_id, stage)
            if not success:
                return

            if stage in PAUSE_AFTER_STAGES:
                self.store.update_task(task_id,
                    status="checkpoint",
                    current_stage=stage,
                    current_step=STAGE_PROGRESS[stage][2],
                    message=f"检查点: 请确认{STAGE_PROGRESS[stage][2]}结果")
                return

        self.store.update_task(task_id,
            status="completed",
            progress=100,
            current_step="完成",
            message="PPT生成完成！")

    async def rerun_page(self, task_id: str, page_number: int):
        """单页重跑：只重新生成指定页的内容"""
        task = self.store.get_task(task_id)
        if not task:
            return

        content_result = self.store.get_stage_result(task_id, "content")
        outline_result = self.store.get_stage_result(task_id, "outline")
        parse_result = self.store.get_stage_result(task_id, "parse")
        analyze_result = self.store.get_stage_result(task_id, "analyze")

        if not all([content_result, outline_result, parse_result, analyze_result]):
            raise RuntimeError("缺少前置阶段结果，无法重跑单页")

        from pipeline.content_filler import ContentFiller
        from models.slide_spec import (
            RawContent, TableData, AnalysisResult, OutlineResult,
        )

        raw_content = self._rebuild_raw_content(parse_result)
        analysis = AnalysisResult.from_dict(analyze_result)
        outline = OutlineResult.from_dict(outline_result)

        llm = self._get_llm_for_stage("content")
        filler = ContentFiller(llm)

        new_content = filler.fill_single_page(
            page_number, raw_content, analysis, outline
        )

        if new_content is None:
            raise RuntimeError(f"无法找到第{page_number}页的大纲")

        # 替换content结果中的对应页
        from models.slide_spec import ContentResult
        cr = ContentResult.from_dict(content_result)
        for i, slide in enumerate(cr.slides):
            if slide.page_number == page_number:
                cr.slides[i] = new_content
                break

        self.store.save_stage_result(task_id, "content", cr.to_dict())
        self._sync_task_fields(task_id, "content", cr.to_dict())

    async def _execute_stage(self, task_id: str, stage: str) -> bool:
        """执行单个Pipeline阶段"""
        progress_start, progress_end, step_name = STAGE_PROGRESS.get(
            stage, (0, 0, stage)
        )

        self.store.update_stage(task_id, stage,
            status="running",
            started_at=self._now())
        self.store.update_task(task_id,
            current_step=step_name,
            current_stage=stage,
            progress=progress_start,
            message=f"正在执行: {step_name}...")

        try:
            task = self.store.get_task(task_id)
            result = await self._run_stage_logic(task_id, stage, task)

            if result is None:
                self.store.update_stage(task_id, stage,
                    status="completed",
                    completed_at=self._now())
                self.store.update_task(task_id, progress=progress_end)
                return True

            self.store.save_stage_result(task_id, stage, result)

            msg = self._build_stage_message(stage, result)
            self.store.update_task(task_id,
                progress=progress_end,
                message=msg)

            self._sync_task_fields(task_id, stage, result)

            return True

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.store.update_stage(task_id, stage,
                status="failed",
                error=str(e),
                completed_at=self._now())
            self.store.update_task(task_id,
                status="failed",
                error=str(e),
                message=f"{step_name}失败: {str(e)}")
            return False

    async def _run_stage_logic(self, task_id: str, stage: str, task: Dict) -> Optional[Dict]:
        """每个阶段的具体执行逻辑 — 在线程池中运行，避免阻塞事件循环"""

        if stage == "parse":
            return await asyncio.to_thread(self._run_parse, task)

        elif stage == "analyze":
            return await asyncio.to_thread(self._run_analyze, task_id, task)

        elif stage == "outline":
            return await asyncio.to_thread(self._run_outline, task_id, task)

        elif stage == "content":
            return await asyncio.to_thread(self._run_content, task_id, task)

        elif stage == "build":
            return await asyncio.to_thread(self._run_build, task_id, task)

        return None

    # ================================================================
    # 阶段实现
    # ================================================================

    def _run_parse(self, task: Dict) -> Dict:
        """parse: 输入解析"""
        from pipeline.layer1_input import InputRouter

        router = InputRouter()
        if task.get("file_path"):
            raw_content = router.parse_file(task["file_path"])
        else:
            raw_content = router.parse_text(task.get("content", ""))

        return {
            "source_type": raw_content.source_type,
            "text_length": len(raw_content.raw_text),
            "table_count": len(raw_content.tables),
            "image_count": len(raw_content.images),
            "detected_language": raw_content.detected_language,
            "raw_text_preview": raw_content.raw_text[:500],
            "tables": [
                {
                    "sheet": t.source_sheet,
                    "headers": t.headers,
                    "row_count": len(t.rows),
                }
                for t in raw_content.tables
            ],
            "_raw_text": raw_content.raw_text,
            "_tables": [
                {"headers": t.headers, "rows": t.rows, "source_sheet": t.source_sheet}
                for t in raw_content.tables
            ],
            "_images": [
                {"file_path": img.file_path, "description": img.description}
                for img in raw_content.images
            ],
            "_metadata": raw_content.metadata,
        }

    def _run_analyze(self, task_id: str, task: Dict) -> Dict:
        """analyze: 数据分析（纯代码计算 + 可选LLM辅助）"""
        from pipeline.data_analyzer import DataAnalyzer
        from models.slide_spec import RawContent, TableData

        parse_result = self.store.get_stage_result(task_id, "parse")
        if not parse_result:
            raise RuntimeError("缺少parse阶段结果")

        raw_content = self._rebuild_raw_content(parse_result)

        # 尝试获取LLM用于辅助分析（非必须）
        llm = None
        try:
            llm = self._get_llm_for_stage("analyze")
        except Exception:
            pass

        analyzer = DataAnalyzer(llm)
        analysis = analyzer.analyze(raw_content)

        return analysis.to_dict()

    def _run_outline(self, task_id: str, task: Dict) -> Dict:
        """outline: 大纲生成（检查点1）"""
        from pipeline.outline_generator import OutlineGenerator
        from models.slide_spec import RawContent, AnalysisResult

        parse_result = self.store.get_stage_result(task_id, "parse")
        analyze_result = self.store.get_stage_result(task_id, "analyze")

        if not parse_result:
            raise RuntimeError("缺少parse阶段结果")
        if not analyze_result:
            raise RuntimeError("缺少analyze阶段结果")

        raw_content = self._rebuild_raw_content(parse_result)
        analysis = AnalysisResult.from_dict(analyze_result)

        llm = self._get_llm_for_stage("outline")
        generator = OutlineGenerator(llm)

        outline = generator.generate(
            raw_content=raw_content,
            analysis=analysis,
            title=task.get("title", ""),
            target_audience=task.get("target_audience", "管理层"),
            scenario=task.get("scenario", ""),
            page_count_hint=0,
        )

        # 合并用户补充数据到outline
        supplements = self.store.get_supplemental_data(task_id, stage="outline")
        if supplements:
            self._apply_supplements_to_outline(outline, supplements)

        return outline.to_dict()

    def _run_content(self, task_id: str, task: Dict) -> Dict:
        """content: 内容填充（检查点2）"""
        from pipeline.content_filler import ContentFiller
        from models.slide_spec import (
            RawContent, AnalysisResult, OutlineResult, ContentResult,
        )

        parse_result = self.store.get_stage_result(task_id, "parse")
        analyze_result = self.store.get_stage_result(task_id, "analyze")
        outline_result = self.store.get_stage_result(task_id, "outline")

        if not all([parse_result, analyze_result, outline_result]):
            raise RuntimeError("缺少前置阶段结果")

        raw_content = self._rebuild_raw_content(parse_result)
        analysis = AnalysisResult.from_dict(analyze_result)
        outline = OutlineResult.from_dict(outline_result)

        llm = self._get_llm_for_stage("content")
        filler = ContentFiller(llm)

        slides = filler.fill_all(raw_content, analysis, outline)

        # 合并用户补充数据
        supplements = self.store.get_supplemental_data(task_id, stage="content")
        if supplements:
            self._apply_supplements_to_content(slides, supplements)

        content_result = ContentResult(
            slides=slides,
            total_pages=len(outline.items),
            failed_pages=[s.page_number for s in slides if s.is_failed],
        )

        return content_result.to_dict()

    def _run_build(self, task_id: str, task: Dict) -> Dict:
        """build: 视觉设计+图表+布局+PPT输出"""
        from pipeline.layer4_visual import VisualDesigner
        from pipeline.layer5_chart import ChartGenerator
        from pipeline.layer6_output import PPTBuilder
        from models.slide_spec import (
            PresentationSpec, SlideSpec, SlideType, TextBlock,
            NarrativeRole, ContentPattern, VisualTheme, BrandKit,
            ChartSpec, ChartType, ChartSeries,
            DiagramSpec, DiagramNode, DiagramEdge,
        )

        outline_result = self.store.get_stage_result(task_id, "outline")
        content_result = self.store.get_stage_result(task_id, "content")

        if not outline_result or not content_result:
            raise RuntimeError("缺少大纲或内容结果，无法构建PPT")

        from models.slide_spec import OutlineResult, ContentResult, AnalysisResult, EnrichedTableData
        outline = OutlineResult.from_dict(outline_result)
        content = ContentResult.from_dict(content_result)

        # 加载 enriched_tables 用于图表数据校验
        enriched_tables: list[EnrichedTableData] = []
        try:
            analyze_result = self.store.get_stage_result(task_id, "analyze")
            if analyze_result:
                analysis = AnalysisResult.from_dict(analyze_result)
                enriched_tables = analysis.enriched_tables
        except Exception as e:
            print(f"[build] 加载enriched_tables失败（兼容旧数据）: {e}")

        language = task.get("language", "zh")
        total_pages = len(outline.items)

        # content 阶段的页面索引
        content_by_page = {s.page_number: s for s in content.slides}

        # ── 构建 SlideSpec 列表（完整映射 content → SlideSpec）──
        slides = []
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

            # narrative_arc: 根据页面位置推断
            if idx == 0:
                slide.narrative_arc = NarrativeRole.OPENING
            elif idx == total_pages - 1:
                slide.narrative_arc = NarrativeRole.CLOSING
            elif idx == 1:
                slide.narrative_arc = NarrativeRole.CONTEXT
            else:
                slide.narrative_arc = NarrativeRole.EVIDENCE

            # 取 content 阶段的页面内容（跳过失败页面）
            page_content = content_by_page.get(item.page_number)
            if page_content and getattr(page_content, 'is_failed', False):
                print(f"[build] 跳过失败页面 {item.page_number}: {getattr(page_content, 'error_message', '')}")
                continue
            if page_content:
                # text_blocks（降级处理：如果为空则从 takeaway 生成占位内容）
                slide.text_blocks = page_content.text_blocks
                if not slide.text_blocks:
                    from models.slide_spec import TextBlock
                    slide.text_blocks = [
                        TextBlock(content=item.takeaway_message, level=0, is_bold=True),
                    ]
                    if getattr(item, 'supporting_hint', ''):
                        slide.text_blocks.append(
                            TextBlock(content=item.supporting_hint, level=1)
                        )
                # source_note
                slide.source_note = page_content.source_note

                # ── chart_suggestion → ChartSpec（校验+回填真实数据）──
                if page_content.chart_suggestion:
                    slide.charts = self._convert_chart_suggestion(
                        page_content.chart_suggestion
                    )
                    if slide.charts and enriched_tables:
                        slide.charts = [
                            self._validate_and_fix_chart(c, enriched_tables)
                            for c in slide.charts
                        ]

                # ── diagram_spec (ContentDiagramSpec) → DiagramSpec ──
                if page_content.diagram_spec:
                    diag = self._convert_diagram_spec(
                        page_content.diagram_spec
                    )
                    if diag:
                        slide.diagrams = [diag]

                # ── visual_block（传递到SlideSpec供版式选择和渲染）──
                if getattr(page_content, 'visual_block', None):
                    slide.visual_block = page_content.visual_block

                # ── primary_visual 冲突仲裁 ──
                pv = getattr(page_content, 'primary_visual', '') or ''
                if not pv:
                    pv = self._infer_primary_visual_from_content(page_content)
                slide.primary_visual = pv

                if pv == 'chart':
                    slide.diagrams = []
                    slide.visual_block = None
                elif pv == 'diagram':
                    slide.charts = []
                    slide.visual_block = None
                elif pv == 'visual_block':
                    slide.charts = []
                    slide.diagrams = []
                elif pv == 'text_only':
                    slide.charts = []
                    slide.diagrams = []
                    slide.visual_block = None
            else:
                # 无 content 数据：从大纲生成最低限度内容
                from models.slide_spec import TextBlock
                slide.text_blocks = [
                    TextBlock(content=item.takeaway_message, level=0, is_bold=True),
                ]
                if getattr(item, 'supporting_hint', ''):
                    slide.text_blocks.append(
                        TextBlock(content=item.supporting_hint, level=1)
                    )

            slides.append(slide)

        # ── 分发原材料图片到合适的 content slide ──
        # 从 layer1 解析出的 RawContent 中取图片（raw_content 作为 stage result 持久化）
        try:
            parse_result = self.store.get_stage_result(task_id, "parse") or {}
            raw_images = parse_result.get("_images") or parse_result.get("images") or []
            # 取出文件路径列表，过滤不存在的
            image_paths = []
            for img in raw_images:
                path = img.get("file_path") if isinstance(img, dict) else getattr(img, "file_path", "")
                if path and os.path.exists(path):
                    image_paths.append(path)
            if image_paths:
                self._distribute_pictures(slides, image_paths)
        except Exception as e:
            print(f"[build] 图片分发失败，已跳过: {e}")

        # Layer 4: 视觉设计
        designer = VisualDesigner()
        slides = designer.design_slides(slides, language=language)

        # Layer 5: LLM 辅助图表（如果 content 没有给出图表建议，尝试补充）
        for slide in slides:
            if not slide.charts and slide.slide_type in (
                SlideType.DATA, SlideType.CONTENT
            ) and slide.content_pattern in (
                ContentPattern.LEFT_CHART_RIGHT_TEXT,
                ContentPattern.LEFT_TEXT_RIGHT_CHART,
                ContentPattern.DATA_DASHBOARD,
            ):
                try:
                    llm = self._get_llm_for_stage("build")
                    chart_gen = ChartGenerator(llm, enriched_tables=enriched_tables)
                    chart = chart_gen._generate_chart(slide)
                    if chart:
                        if enriched_tables:
                            chart = self._validate_and_fix_chart(chart, enriched_tables)
                        slide.charts.append(chart)
                except Exception as e:
                    print(f"[build] 图表生成失败 slide {slide.slide_index}: {e}")

        # Layer 6: PPT构建
        pres_title = task.get("title", "") or "演示文稿"
        pres_spec = PresentationSpec(
            title=pres_title,
            slides=slides,
            language=language,
        )

        builder = PPTBuilder()
        output_path = builder.build(pres_spec)

        self.store.update_task(task_id, output_file=output_path)

        chart_count = sum(len(s.charts) for s in slides)
        diagram_count = sum(len(s.diagrams) for s in slides)

        return {
            "output_file": output_path,
            "slide_count": len(slides),
            "chart_count": chart_count,
            "diagram_count": diagram_count,
            "file_name": output_path.split("/")[-1] if output_path else None,
        }

    def _distribute_pictures(self, slides: list, image_paths: list[str]):
        """
        把原材料图片平均分发到 content 类 slide 上：跳过 title/agenda/section_divider/
        summary；优先给没有 chart/diagram 的页面，每页最多 1 张。剩余图片循环塞入
        后续 content 页面。
        """
        from models.slide_spec import SlideType as _ST
        skip_types = {_ST.TITLE, _ST.AGENDA, _ST.SECTION_DIVIDER, _ST.SUMMARY}
        candidates = [
            s for s in slides
            if s.slide_type not in skip_types and not s.charts and not s.diagrams
        ]
        if not candidates:
            candidates = [s for s in slides if s.slide_type not in skip_types]
        if not candidates:
            return
        for i, path in enumerate(image_paths):
            target = candidates[i % len(candidates)]
            target.pictures.append(path)
        print(f"[build] 已分发 {len(image_paths)} 张原材料图片到 "
              f"{min(len(image_paths), len(candidates))} 个 slide")

    def _convert_chart_suggestion(self, cs) -> list:
        """将 content 阶段的 ChartSuggestion 转为 ChartSpec 列表"""
        try:
            chart_type = ChartType(cs.chart_type)
        except ValueError:
            chart_type = ChartType.COLUMN

        series = [
            ChartSeries(
                name=s.get("name", ""),
                values=s.get("values", []),
            )
            for s in cs.series
        ]

        chart = ChartSpec(
            chart_type=chart_type,
            title=cs.title,
            categories=cs.categories,
            series=series,
            so_what=cs.so_what,
            show_legend=len(series) > 1,
            show_data_labels=True,
        )
        return [chart]

    def _convert_diagram_spec(self, cds) -> Optional[DiagramSpec]:
        """将 content 阶段的 ContentDiagramSpec 转为 DiagramSpec"""
        from models.slide_spec import (
            ProcessFlowSpec, ArchitectureSpec, RelationshipSpec, FrameworkSpec,
        )

        nodes = []
        edges = []

        if cds.process_flow:
            pf = cds.process_flow
            for n in pf.nodes:
                nodes.append(DiagramNode(
                    node_id=str(n.get("id", len(nodes) + 1)),
                    label=n.get("label", ""),
                    sublabel=n.get("desc", ""),
                ))
            for c in pf.connections:
                edges.append(DiagramEdge(
                    from_id=str(c.get("from", "")),
                    to_id=str(c.get("to", "")),
                    label=c.get("label", ""),
                ))
            return DiagramSpec(
                diagram_type="process_flow",
                nodes=nodes,
                edges=edges,
                layout_direction="LR" if pf.direction == "horizontal" else "TB",
                title=cds.title,
            )

        elif cds.relationship:
            rs = cds.relationship
            for n in rs.nodes:
                nodes.append(DiagramNode(
                    node_id=str(n.get("id", len(nodes) + 1)),
                    label=n.get("label", ""),
                ))
            for e in rs.edges:
                edges.append(DiagramEdge(
                    from_id=str(e.get("from", "")),
                    to_id=str(e.get("to", "")),
                    label=e.get("label", ""),
                ))
            return DiagramSpec(
                diagram_type="relationship",
                nodes=nodes,
                edges=edges,
                title=cds.title,
            )

        elif cds.architecture:
            arch = cds.architecture
            # 将层级结构展平为 nodes + edges
            for layer_idx, layer in enumerate(arch.layers):
                layer_label = layer.get("label", f"Layer {layer_idx + 1}")
                nodes.append(DiagramNode(
                    node_id=f"L{layer_idx}",
                    label=layer_label,
                    group=f"layer_{layer_idx}",
                ))
                for item_idx, item_name in enumerate(layer.get("items", [])):
                    node_id = f"L{layer_idx}_I{item_idx}"
                    nodes.append(DiagramNode(
                        node_id=node_id,
                        label=item_name,
                        group=f"layer_{layer_idx}",
                    ))
                    edges.append(DiagramEdge(
                        from_id=f"L{layer_idx}",
                        to_id=node_id,
                    ))
            # 层间连接
            for i in range(len(arch.layers) - 1):
                edges.append(DiagramEdge(
                    from_id=f"L{i}",
                    to_id=f"L{i + 1}",
                ))
            return DiagramSpec(
                diagram_type="architecture",
                nodes=nodes,
                edges=edges,
                title=cds.title,
            )

        elif cds.framework:
            fw = cds.framework
            if fw.variant == "swot":
                for quad, items in [
                    ("top_left", fw.strengths), ("top_right", fw.weaknesses),
                    ("bottom_left", fw.opportunities), ("bottom_right", fw.threats),
                ]:
                    label_map = {
                        "top_left": "Strengths", "top_right": "Weaknesses",
                        "bottom_left": "Opportunities", "bottom_right": "Threats",
                    }
                    nodes.append(DiagramNode(
                        node_id=quad,
                        label=label_map[quad],
                        group=quad,
                    ))
                    for j, item in enumerate(items):
                        nodes.append(DiagramNode(
                            node_id=f"{quad}_{j}",
                            label=item,
                            group=quad,
                        ))
            elif fw.variant in ("matrix_2x2",) and fw.quadrants:
                for q in fw.quadrants:
                    pos = q.get("position", "top_left")
                    nodes.append(DiagramNode(
                        node_id=pos,
                        label=q.get("label", ""),
                        group=pos,
                    ))
                    for j, item in enumerate(q.get("items", [])):
                        nodes.append(DiagramNode(
                            node_id=f"{pos}_{j}",
                            label=item,
                            group=pos,
                        ))
            elif fw.variant == "pyramid" and fw.pyramid_levels:
                for i, level in enumerate(fw.pyramid_levels):
                    nodes.append(DiagramNode(
                        node_id=f"P{i}",
                        label=level.get("label", ""),
                        sublabel=level.get("desc", ""),
                    ))
                    if i > 0:
                        edges.append(DiagramEdge(from_id=f"P{i-1}", to_id=f"P{i}"))
            elif fw.variant == "funnel" and fw.funnel_stages:
                for i, stage in enumerate(fw.funnel_stages):
                    nodes.append(DiagramNode(
                        node_id=f"F{i}",
                        label=stage.get("label", ""),
                        sublabel=str(stage.get("value", "")),
                    ))
                    if i > 0:
                        edges.append(DiagramEdge(from_id=f"F{i-1}", to_id=f"F{i}"))

            return DiagramSpec(
                diagram_type="framework",
                nodes=nodes,
                edges=edges,
                title=cds.title,
            )

        return None

    # ================================================================
    # primary_visual 推断（向下兼容旧数据）
    # ================================================================

    @staticmethod
    def _infer_primary_visual_from_content(page_content) -> str:
        """旧数据没有 primary_visual 时，从实际生成的内容推断"""
        if getattr(page_content, 'chart_suggestion', None):
            return 'chart'
        if getattr(page_content, 'diagram_spec', None):
            return 'diagram'
        vb = getattr(page_content, 'visual_block', None)
        if vb and getattr(vb, 'block_type', 'bullet_list') != 'bullet_list':
            return 'visual_block'
        return 'text_only'

    # ================================================================
    # 图表数据校验（用真实表格数据替换LLM编造的数字）
    # ================================================================

    def _validate_and_fix_chart(self, chart, enriched_tables: list):
        """用enriched_tables的真实数据校验/替换LLM编造的图表数据"""
        if not enriched_tables or not chart.categories or not chart.series:
            return chart

        matched = self._find_matching_table_data(chart, enriched_tables)
        if not matched:
            return chart

        table, cat_col_idx, val_cols = matched

        # 用真实数据重建 categories 和 series
        real_categories = []
        real_rows = []
        for row in table.original.rows:
            if cat_col_idx < len(row) and row[cat_col_idx] is not None:
                real_categories.append(str(row[cat_col_idx]))
                real_rows.append(row)

        if not real_categories:
            return chart

        # 重建每个 series 的 values
        new_series = []
        for si, (val_col_idx, col_name) in enumerate(val_cols):
            values = []
            for row in real_rows:
                if val_col_idx < len(row):
                    v = row[val_col_idx]
                    if isinstance(v, (int, float)):
                        values.append(float(v))
                    elif isinstance(v, str):
                        try:
                            cleaned = v.replace(",", "").replace("%", "").replace("亿", "").replace("万", "").strip()
                            values.append(float(cleaned))
                        except (ValueError, TypeError):
                            values.append(0.0)
                    else:
                        values.append(0.0)
                else:
                    values.append(0.0)
            if values:
                series_name = chart.series[si].name if si < len(chart.series) else col_name
                from models.slide_spec import ChartSeries
                new_series.append(ChartSeries(name=series_name, values=values))

        if new_series:
            chart.categories = real_categories
            chart.series = new_series
            print(f"[build] 图表 '{chart.title}' 已用真实表格数据替换")

        return chart

    def _find_matching_table_data(self, chart, enriched_tables: list):
        """
        模糊匹配：找到chart对应的表格、分类列、数值列。
        返回 (enriched_table, category_col_idx, [(value_col_idx, col_name), ...]) 或 None。
        """
        chart_title = (chart.title or "").lower()
        chart_cats = [str(c).lower() for c in chart.categories]
        series_names = [s.name.lower() for s in chart.series] if chart.series else []

        best_match = None
        best_score = 0

        for et in enriched_tables:
            t = et.original
            if not t.headers or not t.rows:
                continue

            headers_lower = [str(h).lower() for h in t.headers]

            # 找分类列：哪一列的值与 chart.categories 最匹配
            for col_idx in range(len(t.headers)):
                col_values = []
                for row in t.rows:
                    if col_idx < len(row) and row[col_idx] is not None:
                        col_values.append(str(row[col_idx]).lower())

                # 计算匹配度：chart.categories中有多少出现在该列
                cat_matches = sum(
                    1 for cat in chart_cats
                    if any(cat in cv or cv in cat for cv in col_values)
                )
                if cat_matches < max(1, len(chart_cats) * 0.5):
                    continue

                # 找数值列：按series名称或chart title匹配
                val_cols = []
                for vi, header in enumerate(headers_lower):
                    if vi == col_idx:
                        continue
                    # 检查该列是否数值列
                    is_numeric = vi in {idx for idx, _ in self._get_numeric_cols(t)}
                    if not is_numeric:
                        continue
                    # 匹配度加分
                    name_score = 0
                    for sn in series_names:
                        if sn in header or header in sn:
                            name_score += 3
                    if chart_title and (chart_title in header or header in chart_title):
                        name_score += 2
                    val_cols.append((vi, t.headers[vi], name_score))

                if not val_cols:
                    continue

                # 按匹配度排序，取前N个（N=series数量）
                val_cols.sort(key=lambda x: x[2], reverse=True)
                n_series = max(len(chart.series), 1)
                selected_cols = [(idx, name) for idx, name, _ in val_cols[:n_series]]

                score = cat_matches * 10 + sum(s for _, _, s in val_cols[:n_series])
                if score > best_score:
                    best_score = score
                    best_match = (et, col_idx, selected_cols)

        return best_match

    @staticmethod
    def _get_numeric_cols(table) -> list[tuple[int, str]]:
        """识别表格中的数值列"""
        result = []
        for col_idx, header in enumerate(table.headers):
            numeric_count = 0
            for row in table.rows:
                if col_idx < len(row):
                    val = row[col_idx]
                    if isinstance(val, (int, float)):
                        numeric_count += 1
                    elif isinstance(val, str):
                        try:
                            cleaned = val.replace(",", "").replace("%", "").replace("亿", "").replace("万", "").strip()
                            if cleaned:
                                float(cleaned)
                                numeric_count += 1
                        except ValueError:
                            pass
            if table.rows and numeric_count / len(table.rows) > 0.5:
                result.append((col_idx, header))
        return result

    # ================================================================
    # 辅助方法
    # ================================================================

    def _rebuild_raw_content(self, parse_result: Dict) -> "RawContent":
        """从parse阶段结果重建RawContent对象"""
        from models.slide_spec import RawContent, TableData

        tables = [
            TableData(
                headers=t["headers"],
                rows=t["rows"],
                source_sheet=t.get("source_sheet", ""),
            )
            for t in parse_result.get("_tables", [])
        ]

        return RawContent(
            source_type=parse_result.get("source_type", "text"),
            raw_text=parse_result.get("_raw_text", ""),
            tables=tables,
            detected_language=parse_result.get("detected_language", "zh"),
        )

    def _apply_supplements_to_outline(self, outline, supplements: list):
        """将补充数据融合到大纲"""
        for sup in supplements:
            text = sup.get("text_data", "")
            if text:
                outline.data_gap_suggestions.append(
                    f"用户补充: {text[:100]}"
                )

    def _apply_supplements_to_content(self, slides: list, supplements: list):
        """将补充数据融合到内容"""
        from models.slide_spec import TextBlock

        for sup in supplements:
            text = sup.get("text_data", "")
            page_num = sup.get("page_number")
            if not text:
                continue

            # 如果指定了页码，追加到对应页
            if page_num is not None:
                for slide in slides:
                    if slide.page_number == page_num:
                        slide.text_blocks.append(TextBlock(
                            content=f"[补充数据] {text}",
                            level=1,
                            is_bold=False,
                        ))
                        break

    def _get_llm_for_stage(self, stage: str):
        """根据阶段获取对应的LLM客户端"""
        try:
            from models.model_config import PipelineModelConfig
            from llm_client.factory import get_client
            from storage.encryption import decrypt_api_key

            config_json = self.store.get_setting("default", "pipeline_model_config")
            if config_json:
                config = PipelineModelConfig.model_validate_json(config_json)
                stage_config = config.get_stage_config(stage)

                api_key = stage_config.api_key
                if not api_key:
                    encrypted = self.store.get_api_key("default", stage_config.provider)
                    if encrypted:
                        api_key = decrypt_api_key(encrypted)

                if api_key:
                    return get_client(
                        provider=stage_config.provider,
                        api_key=api_key,
                        model=stage_config.model,
                        base_url=stage_config.base_url,
                    )

                raise ValueError(
                    f"阶段 '{stage}' 未配置API Key。"
                    f"请在系统设置中配置 {stage_config.provider} 的API Key。"
                )
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"获取阶段 '{stage}' LLM客户端失败: {e}")

    def _build_stage_message(self, stage: str, result: Dict) -> str:
        """构建阶段完成消息"""
        messages = {
            "parse": lambda r: f"输入解析完成: {r.get('source_type', 'text')}, {r.get('text_length', 0)}字",
            "analyze": lambda r: f"数据分析完成: {len(r.get('derived_metrics', []))}个指标, {len(r.get('key_findings', []))}个发现",
            "outline": lambda r: f"大纲生成完成: {len(r.get('items', []))}页, 叙事逻辑: {r.get('narrative_logic', '')[:50]}",
            "content": lambda r: f"内容填充完成: {r.get('total_pages', 0)}页, 失败{len(r.get('failed_pages', []))}页",
            "build": lambda r: f"PPT构建完成: {r.get('file_name', '')}",
        }
        builder = messages.get(stage)
        return builder(result) if builder else "阶段完成"

    def _sync_task_fields(self, task_id: str, stage: str, result: Dict):
        """同步更新task表的关键字段"""
        if stage == "outline":
            self.store.update_task(task_id, narrative={
                "narrative_logic": result.get("narrative_logic", ""),
                "page_count": len(result.get("items", [])),
            })
        elif stage == "content":
            self.store.update_task(task_id, slides={
                "total_pages": result.get("total_pages", 0),
                "failed_pages": result.get("failed_pages", []),
            })
        elif stage == "build":
            output_file = result.get("output_file")
            if output_file:
                self.store.update_task(task_id, output_file=output_file)

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.now().isoformat()
