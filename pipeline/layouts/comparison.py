"""Comparison layout — two-column side-by-side with labels and bullets."""
from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class ComparisonContent(BaseModel):
    title: str = Field(default="")
    left_label: str = Field(default="方案A")
    left_bullets: list[str] = Field(default_factory=list, max_length=5)
    right_label: str = Field(default="方案B")
    right_bullets: list[str] = Field(default_factory=list, max_length=5)


class ComparisonLayout:
    name = "comparison"
    content_schema = ComparisonContent
    capacity = Capacity(max_text_chars=400, max_bullet_count=10)

    def from_slide_data(self, slide_data: dict) -> ComparisonContent:
        text_blocks = slide_data.get("text_blocks", [])
        vblock = slide_data.get("visual_block") or {}
        if vblock.get("type") == "comparison_columns" and vblock.get("items"):
            items = vblock["items"]
            mid = len(items) // 2
            left = [it.get("title", it.get("content", ""))[:60] for it in items[:mid]]
            right = [it.get("title", it.get("content", ""))[:60] for it in items[mid:]]
        else:
            body = [b for b in text_blocks if b.get("level", 0) > 0 or b.get("type") == "bullet"]
            half = len(body) // 2
            left = [b.get("content", b.get("text", ""))[:60] for b in body[:max(half, 1)]]
            right = [b.get("content", b.get("text", ""))[:60] for b in body[half:]]
        return ComparisonContent(
            title=slide_data.get("takeaway_message", ""),
            left_bullets=[b for b in left if b][:5],
            right_bullets=[b for b in right if b][:5],
        )

    def build_html(self, content: ComparisonContent, theme_colors: dict,
                   page_number: int = 1, total_slides: int = 1) -> str:
        import html as _html
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        footer = f"P{page_number} / {total_slides}"
        title_escaped = _html.escape(content.title)

        def _bullets(items):
            return "\n".join(
                f'<p style="font-size:13px; color:{text_color}; line-height:1.45; '
                f'margin:0 0 6px 0;">- {_html.escape(b)}</p>'
                for b in items
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
            f'<div style="position:absolute; left:640px; top:96px; width:1px; height:579px; '
            'background-color:#E0E0E0;"></div>\n'
            '\n'
            f'<div style="position:absolute; left:53px; top:101px; width:560px; height:37px; '
            f'background-color:{bg};">\n'
            f'  <p style="font-size:12px; font-weight:bold; color:{primary}; '
            f'margin:5px 8px;">{_html.escape(content.left_label)}</p>\n'
            '</div>\n'
            f'<div style="position:absolute; left:53px; top:149px; width:560px; height:531px; '
            'overflow:hidden;">\n'
            f'{_bullets(content.left_bullets)}\n'
            '</div>\n'
            '\n'
            f'<div style="position:absolute; left:661px; top:101px; width:560px; height:37px; '
            f'background-color:{bg};">\n'
            f'  <p style="font-size:12px; font-weight:bold; color:{primary}; '
            f'margin:5px 8px;">{_html.escape(content.right_label)}</p>\n'
            '</div>\n'
            f'<div style="position:absolute; left:661px; top:149px; width:560px; height:531px; '
            'overflow:hidden;">\n'
            f'{_bullets(content.right_bullets)}\n'
            '</div>\n'
            '\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "本页使用双栏对比布局。建议填写 visual_block（type=comparison_columns），"
            "每个 item 含 {title, content}。text_blocks 可保留 1-2 条对比结论。"
        )
