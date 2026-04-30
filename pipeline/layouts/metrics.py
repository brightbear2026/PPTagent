"""Metrics layout — 3-4 KPI cards with supporting sub-bullets."""
from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class MetricItem(BaseModel):
    label: str = Field(default="")
    value: str = Field(default="")
    unit: str = Field(default="")
    note: str = Field(default="")


class MetricsContent(BaseModel):
    title: str = Field(default="")
    metrics: list[MetricItem] = Field(default_factory=list, max_length=4)
    sub_bullets: list[str] = Field(default_factory=list, max_length=3)


class MetricsLayout:
    name = "metrics"
    content_schema = MetricsContent
    capacity = Capacity(max_text_chars=300, max_bullet_count=4)

    def from_slide_data(self, slide_data: dict) -> MetricsContent:
        text_blocks = slide_data.get("text_blocks", [])
        vblock = slide_data.get("visual_block") or {}
        metrics = []
        if vblock.get("items"):
            for item in vblock["items"][:4]:
                label = item.get("title", item.get("description", ""))
                # Avoid mid-sentence truncation: strip trailing incomplete words
                if label and len(label) > 4 and not label[-1] in "。！？：；，、":
                    label = label.rstrip("可直接损失峰值可达约")
                metrics.append(MetricItem(
                    label=label,
                    value=item.get("value", ""),
                    unit=item.get("unit", ""),
                    note=item.get("description", item.get("trend", "")),
                ))
        sub_bullets = []
        for b in text_blocks:
            if b.get("level", 0) > 0 or b.get("type") == "bullet":
                c = b.get("content", b.get("text", ""))
                if c:
                    sub_bullets.append(c[:80])
        return MetricsContent(
            title=slide_data.get("takeaway_message", ""),
            metrics=metrics,
            sub_bullets=sub_bullets[:3],
        )

    def build_html(self, content: MetricsContent, theme_colors: dict,
                   page_number: int = 1, total_slides: int = 1) -> str:
        import html as _html
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")
        footer = f"P{page_number} / {total_slides}"
        title_escaped = _html.escape(content.title)

        metrics_html = ""
        if content.metrics:
            n = len(content.metrics)
            card_w = min(260, 800 // max(n, 1))
            total_w = card_w * n + 20 * (n - 1)
            start_x = (880 - total_w) // 2 + 40
            for i, m in enumerate(content.metrics):
                x = start_x + i * (card_w + 20)
                metrics_html += (
                    f'<div style="position:absolute; left:{x}px; top:90px; '
                    f'width:{card_w}px; height:120px; background-color:{bg}; '
                    f'border-radius:6px; padding:12px; overflow:hidden;">\n'
                    f'  <p style="font-size:11px; color:{muted}; margin:0 0 2px 0; '
                    f'white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
                    f'{_html.escape(m.label)}</p>\n'
                    f'  <p style="font-size:28px; color:{primary}; font-weight:bold; margin:4px 0;">'
                    f'{_html.escape(m.value)}{_html.escape(m.unit)}</p>\n'
                    f'  <p style="font-size:10px; color:{muted}; margin:0;">{_html.escape(m.note)}</p>\n'
                    '</div>\n'
                )

        sub_html = ""
        for b in content.sub_bullets:
            sub_html += (
                f'<p style="font-size:11px; color:{text_color}; line-height:1.4; '
                f'margin:0 0 4px 0;">- {_html.escape(b)}</p>\n'
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
            f'{metrics_html}'
            '\n'
            f'<div style="position:absolute; left:40px; top:400px; width:880px; height:110px; overflow:hidden;">\n'
            f'{sub_html}'
            '</div>\n'
            '\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "本页以指标卡片为主。必须填写 visual_block（type=kpi_cards），"
            "每个 item 含 {title, value, description}。"
            "text_blocks 仅保留 1-2 条数据解读。"
        )
