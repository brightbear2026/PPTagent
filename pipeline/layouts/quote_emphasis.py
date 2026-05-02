"""Quote Emphasis layout — highlight a single core conclusion with supporting evidence."""
from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class QuoteEmphasisContent(BaseModel):
    title: str = Field(default="", description="Slide title (takeaway_message)")
    quote_text: str = Field(min_length=5, max_length=200, description="Core conclusion to highlight")
    sub_bullets: list[str] = Field(default_factory=list, min_length=3, max_length=5, description="Supporting evidence bullets")


class QuoteEmphasisLayout:
    name = "quote_emphasis"
    content_schema = QuoteEmphasisContent
    capacity = Capacity(max_text_chars=400, max_bullet_count=5)

    def from_slide_data(self, slide_data: dict) -> QuoteEmphasisContent:
        text_blocks = slide_data.get("text_blocks", [])
        body_blocks = [b for b in text_blocks if b.get("level", 0) > 0 or b.get("type") == "bullet"]
        quote = ""
        if body_blocks:
            quote = body_blocks[0].get("content", body_blocks[0].get("text", ""))
        if not quote:
            quote = slide_data.get("takeaway_message", "")
        sub_bullets = []
        for b in body_blocks[1:6]:
            c = b.get("content", b.get("text", ""))
            if c:
                sub_bullets.append(c[:80])
        return QuoteEmphasisContent(
            title=slide_data.get("takeaway_message", ""),
            quote_text=quote[:200],
            sub_bullets=sub_bullets,
        )

    def build_html(
        self,
        content: QuoteEmphasisContent,
        theme_colors: dict[str, str],
        page_number: int = 1,
        total_slides: int = 1,
    ) -> str:
        import html as _html

        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")

        title_escaped = _html.escape(content.title)
        quote_escaped = _html.escape(content.quote_text)
        footer = f"P{page_number} / {total_slides}"

        bullets_html = ""
        for b in content.sub_bullets[:5]:
            bullets_html += (
                f'<p style="font-size:13px; color:{text_color}; line-height:1.5; '
                f'margin:0 0 8px 16px; padding-left:12px; '
                f'border-left:2px solid {primary};">'
                f'{_html.escape(b)}</p>\n'
            )

        return (
            '<!DOCTYPE html>\n'
            '<html><head><meta charset="utf-8"></head>\n'
            f'<body style="width:960px; height:540px; '
            f"font-family:'Microsoft YaHei',Arial,sans-serif; "
            'background-color:#FFFFFF; position:relative; overflow:hidden;">\n'
            '\n'
            f'<div style="position:absolute; top:0; left:0; width:960px; height:6px; '
            f'background-color:{accent};"></div>\n'
            f'<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; '
            f'background-color:{primary};">\n'
            f'  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">{footer}</p>\n'
            '</div>\n'
            '\n'
            f'<div style="position:absolute; left:24px; top:28px; width:4px; height:36px; '
            f'background-color:{primary};"></div>\n'
            f'<h2 style="position:absolute; left:40px; top:22px; width:880px; '
            f'font-size:16px; color:{primary}; font-weight:bold; '
            f'line-height:1.35; overflow:hidden; height:44px;">{title_escaped}</h2>\n'
            '\n'
            f'<div style="position:absolute; left:40px; top:76px; width:880px; height:108px; '
            f'background-color:{bg};">\n'
            f'  <div style="position:absolute; left:0; top:0; width:6px; height:108px; '
            f'background-color:{accent};"></div>\n'
            f'  <p style="position:absolute; left:20px; top:16px; width:844px; '
            f'font-size:17px; color:{primary}; font-weight:bold; '
            f'line-height:1.55; overflow:hidden;">{quote_escaped}</p>\n'
            '</div>\n'
            '\n'
            f'<div style="position:absolute; left:40px; top:198px; width:880px; height:300px; '
            'overflow:hidden;">\n'
            f'{bullets_html}'
            '</div>\n'
            '\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "本布局强调单一核心结论。第1条 text_block 为核心结论（≤60字），"
            "后续 2-4 条为支撑论据。不需要 visual_block。"
        )
