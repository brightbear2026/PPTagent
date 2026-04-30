"""Narrative layout — horizontal timeline with phases."""
from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class PhaseItem(BaseModel):
    label: str = Field(default="")
    title: str = Field(default="")
    desc: str = Field(default="")


class NarrativeContent(BaseModel):
    title: str = Field(default="")
    phases: list[PhaseItem] = Field(default_factory=list, max_length=6)


class NarrativeLayout:
    name = "narrative"
    content_schema = NarrativeContent
    capacity = Capacity(max_text_chars=400, max_bullet_count=6)

    def from_slide_data(self, slide_data: dict) -> NarrativeContent:
        vblock = slide_data.get("visual_block") or {}
        phases = []
        if vblock.get("type") == "step_cards" and vblock.get("items"):
            for idx, it in enumerate(vblock["items"][:6]):
                phases.append(PhaseItem(
                    label=it.get("label", f"阶段{idx + 1}"),
                    title=it.get("title", it.get("name", ""))[:30],
                    desc=it.get("description", it.get("desc", ""))[:60],
                ))
        else:
            text_blocks = slide_data.get("text_blocks", [])
            body = [b for b in text_blocks if b.get("level", 0) > 0 or b.get("type") == "bullet"]
            for idx, b in enumerate(body[:5]):
                c = b.get("content", b.get("text", ""))
                phases.append(PhaseItem(
                    label=f"阶段{idx + 1}",
                    title=f"步骤{idx + 1}",
                    desc=c[:80],
                ))
        return NarrativeContent(
            title=slide_data.get("takeaway_message", ""),
            phases=phases,
        )

    def build_html(self, content: NarrativeContent, theme_colors: dict,
                   page_number: int = 1, total_slides: int = 1) -> str:
        import html as _html
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")
        footer = f"P{page_number} / {total_slides}"
        title_escaped = _html.escape(content.title)

        n = len(content.phases) or 1
        phase_w = min(180, 800 // max(n, 1))
        total_w = phase_w * n + 20 * (n - 1)
        start_x = (880 - total_w) // 2 + 40

        # Timeline line
        line_html = (
            f'<div style="position:absolute; left:{start_x}px; top:140px; '
            f'width:{total_w}px; height:3px; background-color:{primary};"></div>\n'
        )

        phases_html = ""
        for i, ph in enumerate(content.phases):
            x = start_x + i * (phase_w + 20)
            # Circle marker
            phases_html += (
                f'<div style="position:absolute; left:{x + phase_w // 2 - 10}px; top:131px; '
                f'width:20px; height:20px; background-color:{accent}; border-radius:50%;"></div>\n'
            )
            # Label above
            phases_html += (
                f'<p style="position:absolute; left:{x}px; top:100px; width:{phase_w}px; '
                f'font-size:11px; color:{accent}; font-weight:bold; text-align:center; '
                f'margin:0;">{_html.escape(ph.label)}</p>\n'
            )
            # Card below
            phases_html += (
                f'<div style="position:absolute; left:{x}px; top:170px; width:{phase_w}px; '
                f'height:180px; background-color:{bg}; border-radius:4px; padding:10px; '
                f'overflow:hidden;">\n'
                f'  <p style="font-size:13px; color:{primary}; font-weight:bold; '
                f'margin:0 0 6px 0;">{_html.escape(ph.title)}</p>\n'
                f'  <p style="font-size:11px; color:{muted}; line-height:1.35; '
                f'margin:0;">{_html.escape(ph.desc)}</p>\n'
                '</div>\n'
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
            f'{line_html}'
            f'{phases_html}'
            '\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "本页使用时间线布局。必须填写 visual_block（type=step_cards），"
            "每个 item 含 {label, title, description}。"
            "text_blocks 仅保留 1-2 条趋势总结。"
        )
