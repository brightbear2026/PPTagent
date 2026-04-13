"""
主题注册表 - 预定义5个VisualTheme
"""
import copy
from models import VisualTheme


def _make_consulting_formal() -> VisualTheme:
    return VisualTheme(
        theme_id="consulting_formal",
        colors={
            "primary": "#003D6E",
            "secondary": "#005A9E",
            "accent": "#FF6B35",
            "text_dark": "#2D3436",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": [
                "#003D6E", "#FF6B35", "#00A878", "#E17055", "#6C5CE7",
                "#FDA7DF", "#55E6C1", "#F8C291", "#82CCDD", "#B8E994",
            ],
        },
        fonts={"title": "Arial", "subtitle": "Arial", "body": "Calibri", "footnote": "Calibri"},
        font_sizes={"title": 28, "subtitle": 18, "body": 12, "bullet": 11, "footnote": 8, "chart_title": 14, "chart_label": 9},
    )


def _make_tech_modern() -> VisualTheme:
    return VisualTheme(
        theme_id="tech_modern",
        colors={
            "primary": "#2D3436",
            "secondary": "#636E72",
            "accent": "#6C5CE7",
            "text_dark": "#2D3436",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": [
                "#6C5CE7", "#00CEC9", "#FD79A8", "#FDCB6E", "#E17055",
                "#0984E3", "#00B894", "#E84393", "#FAB1A0", "#74B9FF",
            ],
        },
        fonts={"title": "Arial", "subtitle": "Arial", "body": "Calibri", "footnote": "Calibri"},
        font_sizes={"title": 28, "subtitle": 18, "body": 12, "bullet": 11, "footnote": 8, "chart_title": 14, "chart_label": 9},
    )


def _make_business_minimalist() -> VisualTheme:
    return VisualTheme(
        theme_id="business_minimalist",
        colors={
            "primary": "#2D3436",
            "secondary": "#636E72",
            "accent": "#00B894",
            "text_dark": "#2D3436",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": [
                "#2D3436", "#00B894", "#636E72", "#DFE6E9", "#B2BEC3",
                "#55EFC4", "#FFEAA7", "#81ECEC", "#A29BFE", "#FAB1A0",
            ],
        },
        fonts={"title": "Arial", "subtitle": "Arial", "body": "Calibri", "footnote": "Calibri"},
        font_sizes={"title": 26, "subtitle": 16, "body": 12, "bullet": 11, "footnote": 8, "chart_title": 13, "chart_label": 9},
    )


def _make_finance_stable() -> VisualTheme:
    return VisualTheme(
        theme_id="finance_stable",
        colors={
            "primary": "#1B4332",
            "secondary": "#2D6A4F",
            "accent": "#D4A373",
            "text_dark": "#1B4332",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": [
                "#1B4332", "#D4A373", "#2D6A4F", "#E9C46A", "#264653",
                "#E76F51", "#F4A261", "#2A9D8F", "#287271", "#8D99AE",
            ],
        },
        fonts={"title": "Georgia", "subtitle": "Georgia", "body": "Calibri", "footnote": "Calibri"},
        font_sizes={"title": 28, "subtitle": 18, "body": 12, "bullet": 11, "footnote": 8, "chart_title": 14, "chart_label": 9},
    )


def _make_creative_vibrant() -> VisualTheme:
    return VisualTheme(
        theme_id="creative_vibrant",
        colors={
            "primary": "#E17055",
            "secondary": "#00CEC9",
            "accent": "#FDCB6E",
            "text_dark": "#2D3436",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": [
                "#E17055", "#00CEC9", "#FDCB6E", "#6C5CE7", "#00B894",
                "#FD79A8", "#0984E3", "#E84393", "#55EFC4", "#FAB1A0",
            ],
        },
        fonts={"title": "Arial", "subtitle": "Arial", "body": "Calibri", "footnote": "Calibri"},
        font_sizes={"title": 28, "subtitle": 18, "body": 12, "bullet": 11, "footnote": 8, "chart_title": 14, "chart_label": 9},
    )


class ThemeRegistry:
    """视觉主题注册表"""

    _THEMES = {
        "consulting_formal": _make_consulting_formal,
        "tech_modern": _make_tech_modern,
        "business_minimalist": _make_business_minimalist,
        "finance_stable": _make_finance_stable,
        "creative_vibrant": _make_creative_vibrant,
    }

    def get_theme(self, theme_id: str) -> VisualTheme:
        """获取主题（返回副本，避免修改原始定义）"""
        factory = self._THEMES.get(theme_id, _make_consulting_formal)
        return copy.deepcopy(factory())

    def get_default(self) -> VisualTheme:
        return self.get_theme("consulting_formal")

    def list_themes(self) -> list[str]:
        return list(self._THEMES.keys())

    def select_by_context(self, tone: str = "professional") -> VisualTheme:
        """根据整体风格推荐主题"""
        tone_map = {
            "professional": "consulting_formal",
            "tech": "tech_modern",
            "minimalist": "business_minimalist",
            "finance": "finance_stable",
            "creative": "creative_vibrant",
        }
        theme_id = tone_map.get(tone, "consulting_formal")
        return self.get_theme(theme_id)
