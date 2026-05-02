"""Framework Grid layout — 3-6 items in icon-text grid."""
from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity

_AUTO_ICONS = ["🎯", "💡", "📊", "⚙️", "🔍", "🚀"]


class GridItem(BaseModel):
    icon: str = Field(default="📊")
    title: str = Field(default="")
    desc: str = Field(default="")


class FrameworkGridContent(BaseModel):
    title: str = Field(default="")
    items: list[GridItem] = Field(default_factory=list, max_length=6)


class FrameworkGridLayout:
    name = "framework_grid"
    content_schema = FrameworkGridContent
    capacity = Capacity(max_text_chars=400, max_bullet_count=6)

    def from_slide_data(self, slide_data: dict) -> FrameworkGridContent:
        vblock = slide_data.get("visual_block") or {}
        items = []
        if vblock.get("type") == "icon_text_grid" and vblock.get("items"):
            for idx, it in enumerate(vblock["items"][:6]):
                icon = _AUTO_ICONS[idx % len(_AUTO_ICONS)]
                items.append(GridItem(
                    icon=icon,
                    title=it.get("title", "")[:20],
                    desc=it.get("description", it.get("desc", ""))[:60],
                ))
        else:
            text_blocks = slide_data.get("text_blocks", [])
            body = [b for b in text_blocks if b.get("level", 0) > 0 or b.get("type") == "bullet"]
            for idx, b in enumerate(body[:6]):
                icon = _AUTO_ICONS[idx % len(_AUTO_ICONS)]
                c = b.get("content", b.get("text", ""))
                items.append(GridItem(
                    icon=icon,
                    title="",
                    desc=c[:80],
                ))
        return FrameworkGridContent(
            title=slide_data.get("takeaway_message", ""),
            items=items,
        )

    def build_html(self, content: FrameworkGridContent, theme_colors: dict,
                   page_number: int = 1, total_slides: int = 1) -> str:
        import html as _html
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")
        footer = f"P{page_number} / {total_slides}"
        title_escaped = _html.escape(content.title)

        n = len(content.items) or 1
        cols = min(3, n)
        rows = (n + cols - 1) // cols
        card_w = 347
        card_h = 147
        gap_x = 27
        gap_y = 21
        grid_w = cols * card_w + (cols - 1) * gap_x
        start_x = (1173 - grid_w) // 2 + 53

        items_html = ""
        for i, item in enumerate(content.items):
            col = i % cols
            row = i // cols
            x = start_x + col * (card_w + gap_x)
            y = 101 + row * (card_h + gap_y)
            items_html += (
                f'<div style="position:absolute; left:{x}px; top:{y}px; '
                f'width:{card_w}px; height:{card_h}px; background-color:{bg}; '
                f'border-radius:4px; padding:10px;">\n'
                f'  <p style="font-size:20px; margin:0 0 4px 0;">{item.icon}</p>\n'
                f'  <p style="font-size:13px; color:{primary}; font-weight:bold; '
                f'margin:0 0 4px 0;">{_html.escape(item.title)}</p>\n'
                f'  <p style="font-size:11px; color:{muted}; line-height:1.35; '
                f'margin:0;">{_html.escape(item.desc)}</p>\n'
                '</div>\n'
            )

        return (
            '<!DOCTYPE html>\n'
            '<html><head><meta charset="utf-8"></head>\n'
            f'<body style="width:1280px; height:720px; '
            f"font-family:'Microsoft YaHei',Arial,sans-serif; "
            'background-color:#FFFFFF; position:relative; overflow:hidden;">\n'
            '\n'
            f'<div style="position:absolute; top:0; left:0; width:1280px; height:6px; '
            f'background-color:{accent};"></div>\n'
            f'<div style="position:absolute; bottom:0; left:0; width:1280px; height:24px; '
            f'background-color:{primary};">\n'
            f'  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">{footer}</p>\n'
            '</div>\n'
            '\n'
            f'<div style="position:absolute; left:32px; top:28px; width:4px; height:36px; '
            f'background-color:{primary};"></div>\n'
            f'<h2 style="position:absolute; left:53px; top:22px; width:1173px; '
            f'font-size:16px; color:{primary}; font-weight:bold; '
            f'line-height:1.35; overflow:hidden; height:44px;">{title_escaped}</h2>\n'
            '\n'
            f'{items_html}'
            '\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "本页使用象限/网格布局。必须填写 visual_block（type=icon_text_grid），"
            "每个 item 含 {title, description}。text_blocks 仅保留 1 条总结。"
        )
