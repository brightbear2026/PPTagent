"""Call-to-Action layout — closing slide with strong takeaway + action items."""
from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class CTAContent(BaseModel):
    takeaway: str = Field(min_length=8, description="Core conclusion / call to action (15-40 chars)")
    action_items: list[str] = Field(default_factory=list, max_length=3, description="1-3 concrete action steps, each ≤20 chars")
    timeline: str = Field(default="", description="Optional suggested timeline, e.g. '3-6 months'")


class CallToActionLayout:
    name = "call_to_action"
    content_schema = CTAContent
    capacity = Capacity(max_text_chars=200, max_bullet_count=3)

    def from_slide_data(self, slide_data: dict) -> CTAContent:
        body_blocks = [b for b in slide_data.get("text_blocks", []) if b.get("level", 0) > 0]
        return CTAContent(
            takeaway=slide_data.get("takeaway_message", ""),
            action_items=[b.get("content", "") for b in body_blocks][:3],
            timeline="",
        )

    def build_html(
        self,
        content: CTAContent,
        theme_colors: dict[str, str],
        page_number: int = 1,
        total_slides: int = 1,
    ) -> str:
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("background", "#FFFFFF")
        text_color = theme_colors.get("text", "#333333")

        items_html = ""
        for i, item in enumerate(content.action_items, 1):
            items_html += (
                f'<li style="margin-bottom:14px;font-size:20px;color:{text_color};'
                f'line-height:1.4;">{i}. {item}</li>\n'
            )

        timeline_html = ""
        if content.timeline:
            timeline_html = (
                f'<p style="font-size:16px;color:{accent};margin-top:28px;'
                f'font-weight:600;">建议时间窗：{content.timeline}</p>'
            )

        return (
            f'<!DOCTYPE html>\n'
            f'<html><head><meta charset="utf-8"></head>\n'
            f'<body style="margin:0;padding:0;width:960px;height:540px;'
            f'background:{bg};display:flex;flex-direction:column;'
            f'justify-content:center;align-items:center;'
            f"font-family:'Microsoft YaHei','PingFang SC','Helvetica Neue',sans-serif;\">\n"
            f'  <div style="max-width:760px;text-align:center;padding:40px 60px;">\n'
            f'    <h1 style="font-size:36px;color:{primary};line-height:1.3;'
            f'margin-bottom:36px;font-weight:700;">\n'
            f'      {content.takeaway}\n'
            f'    </h1>\n'
            f'    <ul style="list-style:none;padding:0;margin:0;text-align:left;'
            f'display:inline-block;">\n'
            f'      {items_html}'
            f'    </ul>\n'
            f'    {timeline_html}\n'
            f'  </div>\n'
            f'</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "本布局用于 deck 结尾的行动号召页。"
            "内容要求：1个核心结论(takeaway_message, 15-40字) "
            "+ 1-3个具体行动项(level=1 bullet, 每项≤20字) + 可选时间线。"
            "不要写长段落，只写可执行的行动步骤。"
        )
