"""
Layer 4: 视觉设计层主类
为每个SlideSpec选择ContentPattern和VisualTheme
"""
import copy
from typing import List
from models import SlideSpec, ContentPattern, SlideType, VisualTheme
from .pattern_matcher import PatternMatcher
from .theme_registry import ThemeRegistry


# 按语言的字号 / 字体策略
# - 中文衬线/无衬线视觉密度高，需要更大字号 + 更宽行距才能保证可读
# - 英文沿用紧凑的咨询字号
LANGUAGE_FONT_STRATEGY = {
    "zh": {
        "font_sizes": {
            "title": 30, "subtitle": 22, "body": 16, "bullet": 14,
            "footnote": 10, "chart_title": 16, "chart_label": 11,
        },
        "fonts": {
            "title": "Microsoft YaHei",
            "subtitle": "Microsoft YaHei",
            "body": "Microsoft YaHei",
            "footnote": "Microsoft YaHei",
        },
    },
    "en": {
        "font_sizes": {
            "title": 28, "subtitle": 20, "body": 14, "bullet": 12,
            "footnote": 9, "chart_title": 14, "chart_label": 9,
        },
        "fonts": {
            "title": "Calibri",
            "subtitle": "Calibri",
            "body": "Calibri",
            "footnote": "Calibri",
        },
    },
}
LANGUAGE_FONT_STRATEGY["mixed"] = LANGUAGE_FONT_STRATEGY["zh"]


def apply_language_strategy(theme: VisualTheme, language: str) -> VisualTheme:
    """将 language 对应的字体 / 字号策略应用到 theme（就地修改）。"""
    strat = LANGUAGE_FONT_STRATEGY.get(language) or LANGUAGE_FONT_STRATEGY["zh"]
    theme.font_sizes = dict(strat["font_sizes"])
    theme.fonts = dict(strat["fonts"])
    return theme


# ContentPattern → layout_template_id 映射
LAYOUT_TEMPLATE_MAP = {
    ContentPattern.TITLE_ONLY: "title_center",
    ContentPattern.AGENDA_LIST: "agenda_vertical",
    ContentPattern.ARGUMENT_EVIDENCE: "text_top_evidence_bottom",
    ContentPattern.TWO_COLUMN: "split_50_50",
    ContentPattern.THREE_COLUMN: "split_33_33_33",
    ContentPattern.LEFT_CHART_RIGHT_TEXT: "chart_left_60_text_right_40",
    ContentPattern.LEFT_TEXT_RIGHT_CHART: "text_left_40_chart_right_60",
    ContentPattern.MATRIX_2X2: "four_quadrant",
    ContentPattern.TIMELINE_HORIZONTAL: "timeline_bar",
    ContentPattern.PROCESS_FLOW: "process_steps",
    ContentPattern.DATA_DASHBOARD: "text_top_chart_bottom",
    ContentPattern.FULL_TABLE: "full_width_table",
    ContentPattern.KPI_HIGHLIGHT: "kpi_dashboard",
    ContentPattern.STEP_FLOW: "step_cards_horizontal",
    ContentPattern.ICON_GRID: "icon_grid_2x3",
    ContentPattern.STAT_CALLOUT: "stat_callout_center",
}

# slide_type 优先覆盖：某些页面的布局由 slide_type 直接决定，
# 不应被 ContentPattern 推断结果反向覆盖（封面/章节过渡/目录）
SLIDE_TYPE_LAYOUT_OVERRIDE = {
    SlideType.TITLE: "title_center",
    SlideType.AGENDA: "agenda_vertical",
    SlideType.SECTION_DIVIDER: "title_center",
    SlideType.SUMMARY: "text_top_evidence_bottom",
}


class VisualDesigner:
    """
    Layer 4: 视觉设计层
    输入：Layer 3输出的SlideSpec列表
    输出：填充 content_pattern, visual_theme, layout_template_id
    """

    def __init__(self):
        self.pattern_matcher = PatternMatcher()
        self.theme_registry = ThemeRegistry()

    def design_slides(self, slides: List[SlideSpec],
                      language: str = "zh",
                      theme_id: str = "consulting_formal") -> List[SlideSpec]:
        """为所有slide填充视觉设计字段"""
        # 选择全局主题
        base_theme = self.theme_registry.get_theme(theme_id)

        for slide in slides:
            self._design_single_slide(slide, base_theme, language)

        print(f"🎨 Layer 4 完成: 为{len(slides)}页完成了视觉设计")
        return slides

    def _design_single_slide(self, slide: SlideSpec,
                             base_theme: VisualTheme,
                             language: str):
        """设计单页的视觉方案"""
        # 1. 匹配ContentPattern
        pattern = self.pattern_matcher.match(slide)
        slide.content_pattern = pattern

        # 2. 分配layout_template_id：slide_type 强制覆盖优先于 pattern 推断
        override = SLIDE_TYPE_LAYOUT_OVERRIDE.get(slide.slide_type)
        if override:
            slide.layout_template_id = override
        else:
            slide.layout_template_id = LAYOUT_TEMPLATE_MAP.get(
                pattern, "text_top_evidence_bottom"
            )

        # 3. 应用主题：优先使用 slide 自身 language，否则用全局参数
        slide_lang = slide.language or language
        theme = copy.deepcopy(base_theme)
        apply_language_strategy(theme, slide_lang)
        slide.visual_theme = theme
        slide.language = slide_lang
