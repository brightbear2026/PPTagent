"""Image Text Grid layout — 3-4 cards with image placeholder + text."""
from pydantic import BaseModel, Field

from pipeline.layouts.base import CANVAS_W, CANVAS_H, Capacity


class GridImageItem(BaseModel):
    title: str = Field(default="")
    description: str = Field(default="")
    image_caption: str = Field(default="")
    image_path: str = Field(default="", description="Real image file path (R32)")


class ImageTextGridContent(BaseModel):
    title: str = Field(default="")
    items: list[GridImageItem] = Field(default_factory=list, min_length=3, max_length=4)


class ImageTextGridLayout:
    name = "image_text_grid"
    content_schema = ImageTextGridContent
    capacity = Capacity(max_text_chars=350, max_bullet_count=4)

    def from_slide_data(self, slide_data: dict) -> ImageTextGridContent:
        vblock = slide_data.get("visual_block") or {}
        items = []
        if vblock.get("type") == "image_text_grid" and vblock.get("items"):
            for it in vblock["items"][:4]:
                items.append(GridImageItem(
                    title=it.get("title", "")[:30],
                    description=it.get("description", it.get("desc", ""))[:80],
                    image_caption=it.get("image_caption", "")[:20],
                    image_path=it.get("image_path", ""),
                ))
        else:
            text_blocks = slide_data.get("text_blocks", [])
            body = [b for b in text_blocks if b.get("level", 0) > 0 or b.get("type") == "bullet"]
            for b in body[:4]:
                c = b.get("content", b.get("text", ""))
                items.append(GridImageItem(
                    title=c[:25],
                    description=c[25:105] if len(c) > 25 else "",
                ))
        # Ensure minimum 3 items
        while len(items) < 3:
            items.append(GridImageItem(title="…", description=""))
        return ImageTextGridContent(
            title=slide_data.get("takeaway_message", ""),
            items=items,
        )

    def build_html(self, content: ImageTextGridContent, theme_colors: dict,
                   page_number: int = 1, total_slides: int = 1) -> str:
        import html as _html
        import os as _os
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")
        footer = f"P{page_number} / {total_slides}"
        title_escaped = _html.escape(content.title)

        n = len(content.items)
        cols = min(n, 4)
        card_w = 267
        img_h = 120
        card_h = 267
        gap = 20
        grid_w = cols * card_w + (cols - 1) * gap
        start_x = (CANVAS_W - grid_w) // 2

        items_html = ""
        for i, item in enumerate(content.items):
            x = start_x + i * (card_w + gap)
            y = 101
            cap = _html.escape(item.image_caption) if item.image_caption else "示意图"

            # R32: Real image if path exists and file exists
            img_html = ""
            if item.image_path and _os.path.isfile(item.image_path):
                img_html = (
                    f'<img src="{_html.escape(item.image_path)}" '
                    f'style="width:{card_w}px; height:{img_h}px; object-fit:cover;" />'
                )
            else:
                img_html = (
                    f'<p style="font-size:11px; color:#BBBBBB; text-align:center;">{cap}</p>'
                )

            items_html += (
                f'<div style="position:absolute; left:{x}px; top:{y}px; '
                f'width:{card_w}px; height:{card_h}px; background-color:#FFFFFF; '
                f'border:1px solid #E0E0E0; border-radius:4px; overflow:hidden;">\n'
                f'  <div style="width:{card_w}px; height:{img_h}px; '
                f'background-color:#F0F0F0; display:flex; align-items:center; '
                f'justify-content:center; overflow:hidden;">\n'
                f'    {img_html}\n'
                f'  </div>\n'
                f'  <div style="padding:8px 10px;">\n'
                f'    <p style="font-size:12px; color:{primary}; font-weight:bold; '
                f'margin:0 0 4px 0;">{_html.escape(item.title)}</p>\n'
                f'    <p style="font-size:10px; color:{muted}; line-height:1.35; '
                f'margin:0;">{_html.escape(item.description)}</p>\n'
                f'  </div>\n'
                '</div>\n'
            )

        return (
            '<!DOCTYPE html>\n'
            '<html><head><meta charset="utf-8"></head>\n'
            f'<body style="width:{CANVAS_W}px; height:{CANVAS_H}px; '
            f"font-family:'Microsoft YaHei',Arial,sans-serif; "
            'background-color:#FFFFFF; position:relative; overflow:hidden;">\n'
            '\n'
            f'<div style="position:absolute; top:0; left:0; width:{CANVAS_W}px; height:6px; '
            f'background-color:{accent};"></div>\n'
            f'<div style="position:absolute; bottom:0; left:0; width:{CANVAS_W}px; height:24px; '
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
            "本页使用图文卡片网格布局。必须填写 visual_block（type=image_text_grid），"
            "每个 item 含 {title, description, image_caption}。3-4 张卡片。"
            "text_blocks 仅保留 1 条总结。"
        )
