"""Parallel Points layout — 4-6 independent supporting arguments as bullets."""
from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class ParallelPointsContent(BaseModel):
    title: str = Field(default="", description="Slide title (takeaway_message)")
    bullets: list[str] = Field(default_factory=list, min_length=4, max_length=6, description="4-6 independent argument bullets")


class ParallelPointsLayout:
    name = "parallel_points"
    content_schema = ParallelPointsContent
    capacity = Capacity(max_text_chars=400, max_bullet_count=6)

    def from_slide_data(self, slide_data: dict) -> ParallelPointsContent:
        text_blocks = slide_data.get("text_blocks", [])
        body_blocks = [
            b for b in text_blocks
            if b.get("level", 0) > 0 or b.get("type") == "bullet"
        ]
        bullets = []
        for b in body_blocks[:6]:
            c = b.get("content", b.get("text", ""))
            if c:
                bullets.append(c[:80])
        return ParallelPointsContent(
            title=slide_data.get("takeaway_message", ""),
            bullets=bullets,
        )

    def build_html(self, content: ParallelPointsContent, theme_colors: dict,
                   page_number: int = 1, total_slides: int = 1) -> str:
        import html as _html
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")
        footer = f"P{page_number} / {total_slides}"
        title_escaped = _html.escape(content.title)

        has_chart = False  # chart placeholder logic handled elsewhere
        title_w = 1173
        content_w = 1173

        bullets_html = ""
        for b in content.bullets:
            bullets_html += (
                f'<p style="font-size:13px; color:{text_color}; line-height:1.5; '
                f'margin:0 0 8px 0; padding-left:14px; '
                f'border-left:3px solid {primary};">'
                f'{_html.escape(b)}</p>\n'
            )

        chart_ph = ""

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
            f'<h2 style="position:absolute; left:53px; top:22px; width:{title_w}px; '
            f'font-size:16px; color:{primary}; font-weight:bold; '
            f'line-height:1.35; overflow:hidden; height:44px;">{title_escaped}</h2>\n'
            '\n'
            f'<div style="position:absolute; left:53px; top:101px; width:{content_w}px; '
            f'height:560px; overflow:hidden;">\n'
            f'{bullets_html}'
            '</div>\n'
            f'{chart_ph}'
            '\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "本页使用并列论据布局。text_blocks 应包含 4-6 条独立并列的论据，"
            "每条一句话。不需要 visual_block。"
        )
