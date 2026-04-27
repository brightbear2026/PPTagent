"""
主题注册表 - 预定义5个VisualTheme

配色策略：每个主题的主色系 + 强调色双色系，消除"用色过多造成的廉价感"。
chart_palette 由 _build_palette() 自动生成主色深浅变体 + 强调色。
"""
import copy
from models import VisualTheme


def _lighten(hex_color: str, factor: float) -> str:
    """将 hex 颜色按 factor (0=原色, 1=白色) 向白色混合。"""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _build_palette(primary: str, accent: str) -> list[str]:
    """生成 10 色调色板：主色深浅变体 + 强调色 + 灰色。"""
    return [
        primary,                    # 0 深主色
        _lighten(primary, 0.25),    # 1 暗主色
        _lighten(primary, 0.45),    # 2 中主色
        _lighten(primary, 0.65),    # 3 浅主色
        accent,                     # 4 强调色（仅用于关键数据点）
        _lighten(primary, 0.15),    # 5 极暗主色
        _lighten(primary, 0.55),    # 6 中浅主色
        _lighten(primary, 0.80),    # 7 极浅主色
        primary,                    # 8 深主色（重复）
        _lighten(primary, 0.35),    # 9 灰色调主色
    ]


def _make_consulting_formal() -> VisualTheme:
    primary = "#003D6E"
    accent = "#FF6B35"
    return VisualTheme(
        theme_id="consulting_formal",
        colors={
            "primary": primary,
            "secondary": "#005A9E",
            "accent": accent,
            "text_dark": "#2D3436",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": _build_palette(primary, accent),
        },
        fonts={"title": "Arial", "subtitle": "Arial", "body": "Calibri", "footnote": "Calibri"},
        font_sizes={"title": 28, "subtitle": 18, "body": 12, "bullet": 11, "footnote": 8, "chart_title": 14, "chart_label": 9},
    )


def _make_tech_modern() -> VisualTheme:
    primary = "#2D3436"
    accent = "#6C5CE7"
    return VisualTheme(
        theme_id="tech_modern",
        colors={
            "primary": primary,
            "secondary": "#636E72",
            "accent": accent,
            "text_dark": "#2D3436",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": _build_palette(primary, accent),
        },
        fonts={"title": "Arial", "subtitle": "Arial", "body": "Calibri", "footnote": "Calibri"},
        font_sizes={"title": 28, "subtitle": 18, "body": 12, "bullet": 11, "footnote": 8, "chart_title": 14, "chart_label": 9},
    )


def _make_business_minimalist() -> VisualTheme:
    primary = "#2D3436"
    accent = "#00B894"
    return VisualTheme(
        theme_id="business_minimalist",
        colors={
            "primary": primary,
            "secondary": "#636E72",
            "accent": accent,
            "text_dark": "#2D3436",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": _build_palette(primary, accent),
        },
        fonts={"title": "Arial", "subtitle": "Arial", "body": "Calibri", "footnote": "Calibri"},
        font_sizes={"title": 26, "subtitle": 16, "body": 12, "bullet": 11, "footnote": 8, "chart_title": 13, "chart_label": 9},
    )


def _make_finance_stable() -> VisualTheme:
    primary = "#1B4332"
    accent = "#D4A373"
    return VisualTheme(
        theme_id="finance_stable",
        colors={
            "primary": primary,
            "secondary": "#2D6A4F",
            "accent": accent,
            "text_dark": "#1B4332",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": _build_palette(primary, accent),
        },
        fonts={"title": "Georgia", "subtitle": "Georgia", "body": "Calibri", "footnote": "Calibri"},
        font_sizes={"title": 28, "subtitle": 18, "body": 12, "bullet": 11, "footnote": 8, "chart_title": 14, "chart_label": 9},
    )


def _make_creative_vibrant() -> VisualTheme:
    primary = "#E17055"
    accent = "#FDCB6E"
    return VisualTheme(
        theme_id="creative_vibrant",
        colors={
            "primary": primary,
            "secondary": "#00CEC9",
            "accent": accent,
            "text_dark": "#2D3436",
            "text_light": "#636E72",
            "background": "#FFFFFF",
            "chart_palette": _build_palette(primary, accent),
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
