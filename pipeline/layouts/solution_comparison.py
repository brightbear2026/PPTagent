"""Solution Comparison layout — multi-option comparison table with scoring."""
import html as _html

from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class SolutionOption(BaseModel):
    name: str
    is_recommended: bool = False


class CompareCell(BaseModel):
    score: str = "average"
    note: str = ""


class SolutionComparisonContent(BaseModel):
    title: str = Field(default="")
    options: list[SolutionOption] = Field(min_length=2, max_length=4)
    criteria: list[str] = Field(min_length=2, max_length=8)
    cells: list[list[CompareCell]] = Field(default_factory=list)


_SCORE_ICONS = {"best": "&#9679;&#9679;&#9679;", "good": "&#9679;&#9679;&#9675;",
                "average": "&#9679;&#9675;&#9675;", "poor": "&#9675;&#9675;&#9675;"}
_SCORE_COLORS = {"best": "#70AD47", "good": "#5B9BD5", "average": "#FFC000", "poor": "#C00000"}


class SolutionComparisonLayout:
    name = "solution_comparison"
    content_schema = SolutionComparisonContent
    capacity = Capacity(max_text_chars=600, max_bullet_count=8)

    def from_slide_data(self, slide_data: dict) -> SolutionComparisonContent:
        vb = slide_data.get("visual_block") or {}
        items = vb.get("items", [])
        tbs = slide_data.get("text_blocks", [])

        options = []
        criteria = []
        cells = []

        if items:
            first = items[0] if items else {}
            sub = first.get("items", {})
            if isinstance(sub, dict):
                options = [SolutionOption(name=k) for k in list(sub.keys())[:4]]
            elif isinstance(sub, list):
                options = [SolutionOption(name=str(s)) for s in sub[:4]]

            criteria = [it.get("title", it.get("name", f"维度{i+1}")) for it in items[:8]]
            for it in items[:8]:
                sub = it.get("items", {})
                row = []
                if isinstance(sub, dict):
                    for opt in options:
                        v = sub.get(opt.name, {})
                        if isinstance(v, dict):
                            row.append(CompareCell(score=v.get("score", "average"), note=v.get("note", "")))
                        else:
                            row.append(CompareCell(score="average", note=""))
                elif isinstance(sub, list):
                    for idx in range(len(options)):
                        s = sub[idx] if idx < len(sub) else None
                        if isinstance(s, dict):
                            row.append(CompareCell(score=s.get("score", "average"), note=s.get("note", "")))
                        elif isinstance(s, str):
                            row.append(CompareCell(score="average", note=s))
                        else:
                            row.append(CompareCell())
                if not row:
                    row = [CompareCell() for _ in options]
                cells.append(row)

        if not options:
            options = [SolutionOption(name="方案A"), SolutionOption(name="方案B")]
        if not criteria:
            for tb in tbs[:4]:
                c = tb.get("content", tb.get("text", ""))
                if c:
                    criteria.append(c[:20])
            if not criteria:
                criteria = ["评估维度"]
            cells = [[CompareCell() for _ in options] for _ in criteria]

        while len(cells) < len(criteria):
            cells.append([CompareCell() for _ in options])

        return SolutionComparisonContent(
            title=slide_data.get("takeaway_message", ""),
            options=options,
            criteria=criteria,
            cells=cells,
        )

    def build_html(
        self,
        content: SolutionComparisonContent,
        theme_colors: dict[str, str],
        page_number: int = 1,
        total_slides: int = 1,
    ) -> str:
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("bg", "#EEF4FA")
        text_color = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#636E72")
        border = theme_colors.get("border", "#C8D8E8")

        title_e = _html.escape(content.title)
        n_opts = len(content.options)
        table_w = 1173
        label_w = 213
        cell_w = (table_w - label_w) // max(n_opts, 1)

        # Header
        header_html = (
            f'<th style="width:{label_w}px; background:{primary}; color:#FFF; '
            f'font-size:12px; padding:8px; text-align:center; border:1px solid {primary};">维度</th>\n'
        )
        for opt in content.options:
            rec_border = f'border:2px solid {accent};' if opt.is_recommended else ''
            rec_badge = f'<span style="font-size:8px;background:{accent};color:#FFF;padding:1px 4px;border-radius:2px;margin-left:4px;">推荐</span>' if opt.is_recommended else ''
            header_html += (
                f'<th style="width:{cell_w}px; background:{primary}; color:#FFF; '
                f'font-size:12px; padding:8px; text-align:center; '
                f'border:1px solid {primary}; {rec_border}">'
                f'{_html.escape(opt.name)}{rec_badge}</th>\n'
            )

        # Rows
        rows_html = ""
        for r_idx, crit in enumerate(content.criteria):
            bg_color = "#FFFFFF" if r_idx % 2 == 0 else bg
            row_cells = content.cells[r_idx] if r_idx < len(content.cells) else []
            rows_html += f'<tr>\n'
            rows_html += (
                f'  <td style="background:{bg_color}; font-size:11px; font-weight:bold; '
                f'color:{text_color}; padding:6px 8px; border:1px solid {border}; '
                f'white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
                f'{_html.escape(crit)}</td>\n'
            )
            for c_idx in range(n_opts):
                cell = row_cells[c_idx] if c_idx < len(row_cells) else CompareCell()
                icons = _SCORE_ICONS.get(cell.score, "&#9679;&#9675;&#9675;")
                color = _SCORE_COLORS.get(cell.score, muted)
                note_e = _html.escape(cell.note) if cell.note else ""
                rec_bg = f'background:{accent}11;' if (content.options[c_idx].is_recommended if c_idx < len(content.options) else False) else ''
                note_html = f'<br><span style="font-size:9px;color:{muted}">{note_e}</span>' if note_e else ""
                rows_html += (
                    f'  <td style="background:{bg_color}; text-align:center; '
                    f'padding:6px; border:1px solid {border}; {rec_bg}">'
                    f'<span style="color:{color}; font-size:12px; letter-spacing:2px;">{icons}</span>'
                    f'{note_html}'
                    f'</td>\n'
                )
            rows_html += '</tr>\n'

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
            f'<div style="position:absolute; left:53px; top:101px; width:{table_w}px; '
            f'max-height:560px; overflow:auto;">\n'
            f'<table style="border-collapse:collapse; width:{table_w}px;">\n'
            f'<tr>{header_html}</tr>\n'
            f'{rows_html}'
            f'</table>\n</div>\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "方案对比：2-4个方案×3-8个评估维度，单元格含评级（best/good/average/poor）和备注。"
            "visual_block.items[].title=维度，items={}中key=方案名，value=评分。"
        )
