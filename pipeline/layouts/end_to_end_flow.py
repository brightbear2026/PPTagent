"""End-to-End Flow layout — horizontal process flow with stages."""
import html as _html

from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class FlowStage(BaseModel):
    name: str = Field(min_length=1, max_length=15)
    actor: str = ""
    action: str = Field(default="", max_length=40)
    output: str = ""
    duration: str = ""


class EndToEndFlowContent(BaseModel):
    title: str = Field(default="")
    stages: list[FlowStage] = Field(min_length=2, max_length=7)


class EndToEndFlowLayout:
    name = "end_to_end_flow"
    content_schema = EndToEndFlowContent
    capacity = Capacity(max_text_chars=600, max_bullet_count=7)

    def from_slide_data(self, slide_data: dict) -> EndToEndFlowContent:
        vb = slide_data.get("visual_block") or {}
        items = vb.get("items", [])
        tbs = slide_data.get("text_blocks", [])
        stages = []

        if items:
            for it in items[:7]:
                name = it.get("title", it.get("name", ""))
                action = it.get("description", it.get("action", ""))[:40]
                actor = it.get("actor", "")
                output = it.get("output", "")
                duration = it.get("duration", "")
                if name:
                    stages.append(FlowStage(name=name, actor=actor, action=action, output=output, duration=duration))

        if not stages:
            for idx, tb in enumerate(tbs[:7]):
                c = tb.get("content", tb.get("text", ""))
                if c:
                    stages.append(FlowStage(name=f"阶段{idx+1}", action=c[:40]))
        if not stages:
            stages = [FlowStage(name="阶段1"), FlowStage(name="阶段2")]

        return EndToEndFlowContent(
            title=slide_data.get("takeaway_message", ""),
            stages=stages,
        )

    def build_html(
        self,
        content: EndToEndFlowContent,
        theme_colors: dict[str, str],
        page_number: int = 1,
        total_slides: int = 1,
    ) -> str:
        primary = theme_colors.get("primary", "#003D6E")
        secondary = theme_colors.get("secondary", "#005A9E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")
        border = theme_colors.get("border", "#C8D8E8")

        title_e = _html.escape(content.title)
        n = len(content.stages)
        stage_w = min(213, (1173 - (n - 1) * 40) // max(n, 1))
        total_w = n * stage_w + (n - 1) * 40
        start_x = 53 + (1173 - total_w) // 2
        box_h = 213

        stages_html = ""
        stage_colors = [primary, secondary, accent, "#70AD47", "#FFC000", "#5B9BD5", "#C00000"]
        for i, stage in enumerate(content.stages):
            x = start_x + i * (stage_w + 30)
            sc = stage_colors[i % len(stage_colors)]
            name_e = _html.escape(stage.name)
            action_e = _html.escape(stage.action)
            actor_e = _html.escape(stage.actor)
            output_e = _html.escape(stage.output)
            dur_e = _html.escape(stage.duration)

            # Arrow between stages
            arrow = ""
            if i < n - 1:
                arrow_x = x + stage_w
                arrow = (
                    f'<div style="position:absolute; left:{arrow_x}px; top:200px; width:40px; '
                    f'text-align:center; font-size:20px; color:{accent};">&#10132;</div>\n'
                )

            # Stage box
            stages_html += (
                f'<div style="position:absolute; left:{x}px; top:120px; width:{stage_w}px; '
                f'height:{box_h}px; background:#FFFFFF; border-radius:6px; '
                f'border-top:4px solid {sc}; box-shadow:0 1px 3px rgba(0,0,0,0.1);">\n'
                # Stage number badge
                f'  <div style="position:absolute; top:-16px; left:50%; transform:translateX(-50%); '
                f'width:32px; height:32px; background:{sc}; border-radius:50%; '
                f'text-align:center; line-height:32px; font-size:12px; color:#FFF; '
                f'font-weight:bold;">{i+1}</div>\n'
                # Name
                f'  <p style="font-size:13px; font-weight:bold; color:{sc}; '
                f'text-align:center; margin:24px 11px 5px 11px; '
                f'white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{name_e}</p>\n'
            )
            actor_html = f'<p style="font-size:9px; color:{muted}; text-align:center; margin:0 8px 4px 8px;">{actor_e}</p>\n' if actor_e else ""
            action_html = f'<p style="font-size:11px; color:{text_color}; text-align:center; margin:4px 8px; line-height:1.4;">{action_e}</p>\n' if action_e else ""
            output_html = f'<p style="font-size:9px; color:{accent}; text-align:center; margin:4px 8px 0 8px; border-top:1px solid {border}; padding-top:4px;">{output_e}</p>\n' if output_e else ""
            dur_html = f'<p style="font-size:8px; color:{muted}; text-align:center; margin:2px 8px 0 8px;">{dur_e}</p>\n' if dur_e else ""

            stages_html += actor_html + action_html + output_html + dur_html
            stages_html += '</div>\n'
            stages_html += arrow

        footer = f"P{page_number} / {total_slides}"
        return (
            '<!DOCTYPE html>\n<html><head><meta charset="utf-8"></head>\n'
            f'<body style="width:1280px; height:720px; '
            f"font-family:'Microsoft YaHei',Arial,sans-serif; "
            f'background-color:#FFFFFF; position:relative; overflow:hidden;">\n'
            f'<div style="position:absolute; top:0; left:0; width:1280px; height:6px; '
            f'background-color:{accent};"></div>\n'
            f'<div style="position:absolute; bottom:0; left:0; width:1280px; height:24px; '
            f'background-color:{primary};">\n'
            f'  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">{footer}</p>\n'
            '</div>\n'
            f'<div style="position:absolute; left:32px; top:28px; width:4px; height:36px; '
            f'background-color:{primary};"></div>\n'
            f'<h2 style="position:absolute; left:53px; top:22px; width:1173px; '
            f'font-size:16px; color:{primary}; font-weight:bold; '
            f'line-height:1.35; overflow:hidden; height:44px;">{title_e}</h2>\n'
            f'{stages_html}'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "端到端流程：4-7个阶段的横向流程图，每段含名称、执行者(actor)、动作(action)、"
            "产出(output)。用箭头连接各阶段。visual_block.items每项为一个阶段。"
        )
