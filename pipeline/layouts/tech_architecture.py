"""Tech Architecture layout — multi-layer technology stack diagram."""
import html as _html

from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class ArchLayer(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    components: list[str] = Field(default_factory=list, max_length=8)


class TechArchitectureContent(BaseModel):
    title: str = Field(default="")
    layers: list[ArchLayer] = Field(min_length=2, max_length=7)


class TechArchitectureLayout:
    name = "tech_architecture"
    content_schema = TechArchitectureContent
    capacity = Capacity(max_text_chars=500, max_bullet_count=7)

    def from_slide_data(self, slide_data: dict) -> TechArchitectureContent:
        vb = slide_data.get("visual_block") or {}
        items = vb.get("items", [])
        layers = []
        if items:
            for item in items[:7]:
                name = item.get("title", item.get("name", ""))
                comps = item.get("items", item.get("components", []))
                if isinstance(comps, list):
                    comps = [str(c) for c in comps]
                elif isinstance(comps, str):
                    comps = [comps]
                else:
                    comps = []
                if name:
                    layers.append(ArchLayer(name=name, components=comps))

        if not layers:
            tbs = slide_data.get("text_blocks", [])
            for tb in tbs[:7]:
                c = tb.get("content", tb.get("text", ""))
                if c:
                    layers.append(ArchLayer(name=c[:20], components=[]))
        if not layers:
            layers = [ArchLayer(name="应用层", components=[]), ArchLayer(name="基础设施", components=[])]

        return TechArchitectureContent(
            title=slide_data.get("takeaway_message", ""),
            layers=layers,
        )

    def build_html(
        self,
        content: TechArchitectureContent,
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
        n = len(content.layers)
        layer_colors = [primary, secondary, accent, "#70AD47", "#FFC000", "#5B9BD5", "#C00000"]
        available_h = 420
        layer_h = max(50, min(80, available_h // max(n, 1)))
        start_y = 80

        layers_html = ""
        for i, layer in enumerate(content.layers):
            y = start_y + i * (layer_h + 6)
            lc = layer_colors[i % len(layer_colors)]
            name_e = _html.escape(layer.name)
            comps_e = " | ".join(_html.escape(c) for c in layer.components[:8])
            layers_html += (
                f'<div style="position:absolute; left:40px; top:{y}px; width:880px; height:{layer_h}px; '
                f'background-color:{bg}; border-left:6px solid {lc}; border-radius:4px;">\n'
                f'  <div style="position:absolute; left:12px; top:50%; transform:translateY(-50%); '
                f'width:140px; font-size:13px; font-weight:bold; color:{lc}; '
                f'white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{name_e}</div>\n'
                f'  <div style="position:absolute; left:160px; top:50%; transform:translateY(-50%); '
                f'width:710px; font-size:12px; color:{text_color}; '
                f'line-height:1.4;">{comps_e}</div>\n'
                '</div>\n'
            )

        footer = f"P{page_number} / {total_slides}"
        return (
            '<!DOCTYPE html>\n<html><head><meta charset="utf-8"></head>\n'
            f'<body style="width:960px; height:540px; '
            f"font-family:'Microsoft YaHei',Arial,sans-serif; "
            f'background-color:#FFFFFF; position:relative; overflow:hidden;">\n'
            f'<div style="position:absolute; top:0; left:0; width:960px; height:6px; '
            f'background-color:{accent};"></div>\n'
            f'<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; '
            f'background-color:{primary};">\n'
            f'  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">{footer}</p>\n'
            '</div>\n'
            f'<div style="position:absolute; left:24px; top:28px; width:4px; height:36px; '
            f'background-color:{primary};"></div>\n'
            f'<h2 style="position:absolute; left:40px; top:22px; width:880px; '
            f'font-size:16px; color:{primary}; font-weight:bold; '
            f'line-height:1.35; overflow:hidden; height:44px;">{title_e}</h2>\n'
            f'{layers_html}'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "技术架构图：2-7 层横向堆叠层级图（如应用层→平台层→数据层→基础设施），"
            "每层有名称和组件列表。visual_block.items[].title=层名，"
            "visual_block.items[].items[]=组件列表。"
        )
