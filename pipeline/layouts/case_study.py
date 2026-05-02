"""Case Study layout — customer case card with KPIs and quote."""
import html as _html

from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class KPIItem(BaseModel):
    label: str = ""
    value: str = ""
    unit: str = ""


class CaseStudyContent(BaseModel):
    title: str = Field(default="")
    customer_name: str = Field(min_length=1, max_length=30)
    customer_industry: str = ""
    challenge: str = Field(default="", max_length=120)
    solution: str = Field(default="", max_length=120)
    kpis: list[KPIItem] = Field(default_factory=list, max_length=4)
    quote: str = ""
    duration: str = ""


class CaseStudyLayout:
    name = "case_study"
    content_schema = CaseStudyContent
    capacity = Capacity(max_text_chars=500, max_bullet_count=4)

    def from_slide_data(self, slide_data: dict) -> CaseStudyContent:
        vb = slide_data.get("visual_block") or {}
        items = vb.get("items", [])
        tbs = slide_data.get("text_blocks", [])

        customer_name = ""
        customer_industry = ""
        challenge = ""
        solution = ""
        kpis = []
        quote = ""
        duration = ""

        if items:
            customer_name = items[0].get("title", items[0].get("customer", "")) if items else ""
            if not customer_name:
                customer_name = slide_data.get("title", "")[:30]
            for it in items[1:5]:
                label = it.get("title", it.get("label", ""))
                value = it.get("value", "")
                unit = it.get("unit", "")
                if label and value:
                    kpis.append(KPIItem(label=label, value=str(value), unit=unit))

        body_blocks = [b for b in tbs if b.get("level", 0) > 0 or b.get("type") == "bullet"]
        if body_blocks and not challenge:
            challenge = body_blocks[0].get("content", body_blocks[0].get("text", ""))[:120]
        if len(body_blocks) > 1 and not solution:
            solution = body_blocks[1].get("content", body_blocks[1].get("text", ""))[:120]

        if not customer_name:
            customer_name = slide_data.get("title", "客户案例")[:30]
        if not kpis and items:
            for it in items[:3]:
                val = it.get("value", it.get("description", ""))
                if val:
                    kpis.append(KPIItem(label=it.get("title", ""), value=str(val)[:20]))
        if not kpis:
            kpis = [KPIItem(label="KPI", value="--")]

        return CaseStudyContent(
            title=slide_data.get("takeaway_message", ""),
            customer_name=customer_name,
            customer_industry=customer_industry,
            challenge=challenge,
            solution=solution,
            kpis=kpis,
            quote=quote,
            duration=duration,
        )

    def build_html(
        self,
        content: CaseStudyContent,
        theme_colors: dict[str, str],
        page_number: int = 1,
        total_slides: int = 1,
    ) -> str:
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")

        title_e = _html.escape(content.title)
        name_e = _html.escape(content.customer_name)
        ind_e = _html.escape(content.customer_industry)
        ch_e = _html.escape(content.challenge)
        sol_e = _html.escape(content.solution)
        quote_e = _html.escape(content.quote)
        dur_e = _html.escape(content.duration)

        # KPI cards (right side)
        kpi_html = ""
        kpi_count = len(content.kpis) or 1
        kpi_h = min(120, 507 // max(kpi_count, 1))
        for i, kpi in enumerate(content.kpis):
            y = 107 + i * (kpi_h + 11)
            kpi_html += (
                f'<div style="position:absolute; right:32px; top:{y}px; width:267px; height:{kpi_h}px; '
                f'background:{bg}; border-radius:6px; border-left:4px solid {accent}; padding:8px 12px; '
                f'box-sizing:border-box;">\n'
                f'  <p style="font-size:9px; color:{muted}; margin:0 0 2px 0;">{_html.escape(kpi.label)}</p>\n'
                f'  <p style="font-size:22px; color:{accent}; font-weight:bold; margin:0;">'
                f'{_html.escape(kpi.value)}<span style="font-size:11px; color:{muted}; font-weight:normal;">'
                f' {_html.escape(kpi.unit)}</span></p>\n'
                '</div>\n'
            )

        # Customer info + challenge/solution (left side)
        left_w = 907
        dur_html = f'<span style="font-size:10px; color:{muted}; margin-left:12px;">{dur_e}</span>' if dur_e else ""

        footer = f"P{page_number} / {total_slides}"
        quote_html = (
            f'<div style="position:absolute; left:53px; top:427px; width:907px; '
            f'font-size:12px; color:{muted}; font-style:italic; '
            f'line-height:1.5; border-left:3px solid {accent}; '
            f'padding-left:12px;">{quote_e}</div>\n'
        ) if quote_e else ""

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
            # Title
            f'<div style="position:absolute; left:32px; top:28px; width:4px; height:36px; '
            f'background-color:{primary};"></div>\n'
            f'<h2 style="position:absolute; left:53px; top:22px; width:1173px; '
            f'font-size:16px; color:{primary}; font-weight:bold; '
            f'line-height:1.35; overflow:hidden; height:44px;">{title_e}</h2>\n'
            # Customer name
            f'<div style="position:absolute; left:53px; top:107px; width:{left_w}px; '
            f'height:53px; background:{primary}; border-radius:4px;">\n'
            f'  <p style="font-size:16px; color:#FFFFFF; font-weight:bold; margin:14px 21px;">'
            f'{name_e}{dur_html}</p>\n'
            '</div>\n'
            # Challenge
            f'<div style="position:absolute; left:53px; top:181px; width:{left_w}px; '
            f'overflow:hidden;">\n'
            f'  <p style="font-size:11px; color:{muted}; margin:0 0 4px 0;">挑战</p>\n'
            f'  <p style="font-size:13px; color:{text_color}; line-height:1.5; margin:0;">{ch_e}</p>\n'
            '</div>\n'
            # Solution
            f'<div style="position:absolute; left:53px; top:307px; width:{left_w}px; '
            f'overflow:hidden;">\n'
            f'  <p style="font-size:11px; color:{muted}; margin:0 0 4px 0;">解决方案</p>\n'
            f'  <p style="font-size:13px; color:{text_color}; line-height:1.5; margin:0;">{sol_e}</p>\n'
            '</div>\n'
            f'{quote_html}'
            f'{kpi_html}'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "客户案例卡：客户名+行业+实施周期、挑战→方案描述、2-4个KPI大数字。"
            "visual_block.items[0].title=客户名，后续items为KPI（label+value+unit）。"
            "text_blocks前2条分别为挑战和方案。"
        )
