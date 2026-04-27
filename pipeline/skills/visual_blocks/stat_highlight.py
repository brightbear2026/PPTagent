"""
Stat Highlight Skill

单个震撼数字展示——超大字号 + 标签 + 装饰线 + 上下文描述。

质量修复（相比原 ppt_builder.py）：
1. value 字号根据字符数动态调整（不再固定 Pt(60)）
2. 数字下方增加主题色装饰线
3. description 区域增加左右 padding（原来硬编码 1/6 宽度）
"""

from pptx.util import Pt, Emu
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

from models import VisualBlock, VisualBlockItem, Rect
from pipeline.skills.base import RenderingSkill, SkillDescriptor
from pipeline.skills._utils import (
    parse_color, theme_color, fit_font_size, add_centered_text,
)


class StatHighlightSkill(RenderingSkill):

    def descriptor(self) -> SkillDescriptor:
        return SkillDescriptor(
            skill_id="vb_stat_highlight",
            skill_type="visual_block",
            handles_types=["stat_highlight"],
            content_pattern="stat_callout",
        )

    def prompt_fragment(self) -> str:
        return """**stat_highlight**（单个震撼数字）
  items字段: value, title, description
  设计理念: 一句话胜千言——超大字号展示唯一数字，其余弱化
  质量要求: 仅用于全篇最震撼的1个数字；description说明为什么这个数字重要
  反模式: 不要用于多个数字并列展示（用kpi_cards）；不要用于普通增幅（如+5%），仅用于戏剧性数字（+200%、亏损转盈利、行业第一）"""

    def design_tokens(self) -> dict:
        return {
            "value_font_range": (36, 72),  # 超大字号范围
            "decorative_bar_height": 27000,  # ~3px 装饰线
            "desc_padding_ratio": 0.2,       # description 左右 padding 占宽度比
        }

    def render(self, slide, data: VisualBlock, rect, theme) -> bool:
        if isinstance(rect, list):
            rect = rect[0] if rect else None
        if rect is None:
            return False

        item = data.items[0] if data.items else VisualBlockItem()
        tokens = self.design_tokens()

        primary = theme_color(theme, "primary", "#003D6E")
        accent = theme_color(theme, "accent", "#FF6B35")
        text_light = theme_color(theme, "text_light", "#636E72")
        title_font = theme.fonts.get("title", "Arial")
        body_font = theme.fonts.get("body", "Calibri")

        # ── 大数字（字号自适应）──
        value_text = item.value or "—"
        min_pt, max_pt = tokens["value_font_range"]
        font_size = fit_font_size(value_text, max_pt, min_pt)

        val_h = rect.height * 40 // 100
        add_centered_text(
            slide,
            rect.left, rect.top,
            rect.width, val_h,
            value_text,
            font_size=font_size,
            font_name=title_font,
            color=accent,
            bold=True,
        )

        # ── 装饰线（主题色，居中 1/3 宽度）──
        bar_w = rect.width // 3
        bar_left = rect.left + (rect.width - bar_w) // 2
        bar_top = rect.top + val_h + Emu(45720)  # ~0.05 inch gap
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Emu(bar_left), Emu(bar_top),
            Emu(bar_w), Emu(tokens["decorative_bar_height"]),
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = accent
        bar.line.fill.background()

        # ── 标签 ──
        label_top = int(bar_top) + tokens["decorative_bar_height"] + Emu(91440)
        add_centered_text(
            slide,
            rect.left, label_top,
            rect.width, Emu(365760),
            item.title or "",
            font_size=18,
            font_name=body_font,
            color=primary,
            bold=True,
        )

        # ── 上下文描述（增加左右 padding）──
        if item.description:
            padding = int(rect.width * tokens["desc_padding_ratio"])
            desc_top = int(label_top) + Emu(365760)
            add_centered_text(
                slide,
                rect.left + padding, desc_top,
                rect.width - padding * 2,
                rect.height - (desc_top - rect.top),
                item.description,
                font_size=12,
                font_name=body_font,
                color=text_light,
            )

        return True
