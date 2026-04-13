"""
Layer 5: 图表生成层主类
为有数据需求的SlideSpec生成ChartSpec和DiagramSpec
"""
from typing import List
from models import (SlideSpec, ContentPattern, SlideType, NarrativeRole)
from llm_client.glm_client import GLMClient
from .chart_type_selector import ChartTypeSelector
from .chart_spec_builder import ChartSpecBuilder
from .diagram_builder import DiagramBuilder


class ChartGenerator:
    """
    Layer 5: 图表生成层
    输入：Layer 4输出的SlideSpec（已填充 content_pattern, visual_theme）
    输出：填充 charts, diagrams
    """

    def __init__(self, llm_client: GLMClient, enriched_tables=None):
        self.llm = llm_client
        self.chart_type_selector = ChartTypeSelector()
        self.chart_spec_builder = ChartSpecBuilder(llm_client, enriched_tables=enriched_tables)
        self.diagram_builder = DiagramBuilder(llm_client)

    def generate_for_slides(self, slides: List[SlideSpec]) -> List[SlideSpec]:
        """为所有需要的slide生成图表和架构图"""
        chart_count = 0
        diagram_count = 0

        for slide in slides:
            # 跳过标题页和议程页
            if slide.slide_type in (SlideType.TITLE, SlideType.AGENDA):
                continue

            # 判断并生成图表
            if self._needs_chart(slide):
                chart = self._generate_chart(slide)
                if chart:
                    slide.charts.append(chart)
                    chart_count += 1

            # 判断并生成架构图
            if self._needs_diagram(slide):
                diagram = self._generate_diagram(slide)
                if diagram:
                    slide.diagrams.append(diagram)
                    diagram_count += 1

        print(f"📊 Layer 5 完成: 生成{chart_count}个图表, {diagram_count}个架构图")
        return slides

    def _needs_chart(self, slide: SlideSpec) -> bool:
        """判断是否需要图表"""
        # 已有图表的不重复生成
        if slide.charts:
            return False

        pattern = slide.content_pattern
        if pattern in (ContentPattern.LEFT_CHART_RIGHT_TEXT,
                       ContentPattern.LEFT_TEXT_RIGHT_CHART,
                       ContentPattern.DATA_DASHBOARD):
            return True

        # EVIDENCE/ANALYSIS角色通常需要数据支撑
        if slide.narrative_arc in (NarrativeRole.EVIDENCE, NarrativeRole.ANALYSIS):
            if slide.data_references or self._text_has_numbers(slide):
                return True

        return False

    def _needs_diagram(self, slide: SlideSpec) -> bool:
        """判断是否需要拓扑图/架构图"""
        if slide.diagrams:
            return False
        if slide.slide_type == SlideType.DIAGRAM:
            return True
        if slide.content_pattern == ContentPattern.PROCESS_FLOW:
            return True
        return False

    def _generate_chart(self, slide: SlideSpec):
        """生成单个图表规格"""
        chart_type = self.chart_type_selector.select(slide)
        theme_colors = []
        if slide.visual_theme:
            theme_colors = slide.visual_theme.colors.get("chart_palette", [])

        return self.chart_spec_builder.build_from_slide(slide, chart_type, theme_colors)

    def _generate_diagram(self, slide: SlideSpec):
        """生成单个架构图规格"""
        return self.diagram_builder.build_from_slide(slide)

    def _text_has_numbers(self, slide: SlideSpec) -> bool:
        import re
        text = " ".join(b.content for b in slide.text_blocks)
        return bool(re.search(r'\d+\.?\d*%|\d+\.?\d*[亿万]', text))
