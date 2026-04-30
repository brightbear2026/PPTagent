"""Call-to-Action layout — closing slide with strong takeaway + action items."""
import html as _html

from pydantic import BaseModel, Field, model_validator

from pipeline.layouts.base import Capacity


def _char_overlap_ratio(a: str, b: str) -> float:
    """Return ratio of shared prefix chars to shorter string length."""
    if not a or not b:
        return 0.0
    shorter = min(len(a), len(b))
    shared = 0
    for i in range(shorter):
        if a[i] == b[i]:
            shared += 1
        else:
            break
    return shared / max(len(a), len(b))


class CTAContent(BaseModel):
    takeaway: str = Field(min_length=8, description="Core conclusion / call to action (15-40 chars)")
    action_items: list[str] = Field(min_length=3, max_length=5, description="3-5 concrete action steps, each ≤40 chars")
    timeline: str = Field(min_length=1, description="Suggested timeline, e.g. '3-6 months'")

    @model_validator(mode="after")
    def reject_duplicated_action_item(self):
        if not self.takeaway or not self.action_items:
            return self
        first = self.action_items[0]
        overlap = _char_overlap_ratio(self.takeaway, first)
        if overlap > 0.5:
            raise ValueError(
                f"action_items[0] duplicates takeaway (overlap {overlap:.0%}). "
                f"action_items must be distinct concrete next steps, not restate the takeaway."
            )
        return self


class CallToActionLayout:
    name = "call_to_action"
    content_schema = CTAContent
    capacity = Capacity(max_text_chars=200, max_bullet_count=5)

    def from_slide_data(self, slide_data: dict) -> CTAContent:
        body_blocks = [b for b in slide_data.get("text_blocks", []) if b.get("level", 0) > 0]
        action_items = [b.get("content", "") for b in body_blocks][:5]
        return CTAContent(
            takeaway=slide_data.get("takeaway_message", ""),
            action_items=action_items,
            timeline=slide_data.get("timeline", "3-6个月"),
        )

    def build_html(
        self,
        content: CTAContent,
        theme_colors: dict,
        page_number: int = 1,
        total_slides: int = 1,
    ) -> str:
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("background", "#FFFFFF")
        text_color = theme_colors.get("text", "#333333")
        footer = f"P{page_number} / {total_slides}"

        items_html = ""
        for i, item in enumerate(content.action_items, 1):
            items_html += (
                f'<li style="margin-bottom:14px;font-size:20px;color:{text_color};'
                f'line-height:1.4;">{i}. {_html.escape(item)}</li>\n'
            )

        timeline_html = ""
        if content.timeline:
            timeline_html = (
                f'<p style="font-size:16px;color:{accent};margin-top:28px;'
                f'font-weight:600;">建议时间窗：{_html.escape(content.timeline)}</p>'
            )

        return (
            '<!DOCTYPE html>\n'
            '<html><head><meta charset="utf-8"></head>\n'
            f'<body style="margin:0;padding:0;width:960px;height:540px;'
            f'background:{bg};position:relative;overflow:hidden;'
            f"font-family:'Microsoft YaHei','PingFang SC','Helvetica Neue',sans-serif;\">\n"
            '\n'
            f'<div style="position:absolute; top:0; left:0; width:960px; height:6px; '
            f'background-color:{accent};"></div>\n'
            f'<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; '
            f'background-color:{primary};">\n'
            f'  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">{footer}</p>\n'
            '</div>\n'
            '\n'
            f'  <div style="max-width:760px;text-align:center;padding:40px 60px; '
            f'position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);">\n'
            f'    <h1 style="font-size:36px;color:{primary};line-height:1.3;'
            f'margin-bottom:36px;font-weight:700;">\n'
            f'      {_html.escape(content.takeaway)}\n'
            f'    </h1>\n'
            f'    <ul style="list-style:none;padding:0;margin:0;text-align:left;'
            f'display:inline-block;">\n'
            f'      {items_html}'
            f'    </ul>\n'
            f'    {timeline_html}\n'
            f'  </div>\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "本布局用于 deck 结尾的行动号召页。"
            "内容要求：1个核心结论(takeaway_message, 15-40字) "
            "+ 3-5个具体行动项(level=1 bullet, 每项≤40字, 不可重复takeaway) "
            "+ 时间线(timeline字段, 如'3-6个月')。"
            "不要写长段落，只写可执行的行动步骤。"
        )
