"""Chart Focus layout — chart placeholder + annotation bullets on the left."""
from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class ChartFocusContent(BaseModel):
    title: str = Field(default="")
    annotations: list[str] = Field(default_factory=list, min_length=3, max_length=5)
    supporting_text: str = Field(default="", max_length=200)


class ChartFocusLayout:
    name = "chart_focus"
    content_schema = ChartFocusContent
    capacity = Capacity(max_text_chars=300, max_bullet_count=5)

    def from_slide_data(self, slide_data: dict) -> ChartFocusContent:
        text_blocks = slide_data.get("text_blocks", [])
        body_blocks = [
            b for b in text_blocks
            if b.get("level", 0) > 0 or b.get("type") == "bullet"
        ]
        annotations = []
        for b in body_blocks[:5]:
            c = b.get("content", b.get("text", ""))
            if c:
                annotations.append(c[:80])
        return ChartFocusContent(
            title=slide_data.get("takeaway_message", ""),
            annotations=annotations or ["关键发现1", "关键发现2", "关键发现3"],
        )

    def build_html(self, content: ChartFocusContent, theme_colors: dict,
                   page_number: int = 1, total_slides: int = 1) -> str:
        import html as _html
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")
        footer = f"P{page_number} / {total_slides}"
        title_escaped = _html.escape(content.title)

        ann_html = ""
        for a in content.annotations:
            ann_html += (
                f'<p style="font-size:12px; color:{text_color}; line-height:1.4; '
                f'margin:0 0 8px 0; padding-left:10px; '
                f'border-left:2px solid {accent};">'
                f'{_html.escape(a)}</p>\n'
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
            '<div class="placeholder" id="chart-0" style="position:absolute; '
            'left:360px; top:76px; width:556px; height:420px;"></div>\n'
            '\n'
            f'<div style="position:absolute; left:40px; top:76px; width:300px; height:420px; '
            'overflow:hidden;">\n'
            f'{ann_html}'
            '</div>\n'
            '\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "本页以图表为主。chart_suggestion 必须填写。"
            "text_blocks 提供 3-5 条图表解读/标注。"
        )
