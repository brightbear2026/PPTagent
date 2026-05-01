"""Capability Matrix layout — dimension × phase comparison grid."""
import html as _html

from typing import Literal, Optional

from pydantic import BaseModel, Field

from pipeline.layouts.base import Capacity


class MatrixCell(BaseModel):
    status: str = "no"
    note: str = ""


class CapabilityMatrixContent(BaseModel):
    title: str = Field(default="")
    columns: list[str] = Field(min_length=2, max_length=5)
    rows: list[str] = Field(min_length=2, max_length=8)
    cells: list[list[MatrixCell]] = Field(default_factory=list)


_STATUS_ICONS = {"yes": "&#10003;", "no": "&#10007;", "partial": "&#9675;", "planned": "&#9201;"}
_STATUS_COLORS = {"yes": "#70AD47", "no": "#C00000", "partial": "#FFC000", "planned": "#5B9BD5"}


class CapabilityMatrixLayout:
    name = "capability_matrix"
    content_schema = CapabilityMatrixContent
    capacity = Capacity(max_text_chars=600, max_bullet_count=8)

    def from_slide_data(self, slide_data: dict) -> CapabilityMatrixContent:
        vb = slide_data.get("visual_block") or {}
        items = vb.get("items", [])
        columns = []
        rows = []
        cells = []

        if items:
            first = items[0] if items else {}
            sub_keys = [k for k in first.get("items", first) if isinstance(first.get(k), dict)]
            if not sub_keys and isinstance(first.get("items"), list):
                sub_items = first["items"]
                if isinstance(sub_items, list) and sub_items:
                    if isinstance(sub_items[0], dict):
                        columns = list(sub_items[0].keys())[:5]
                    else:
                        columns = [f"阶段{i+1}" for i in range(min(5, len(sub_items)))]

            rows = [it.get("title", it.get("name", f"维度{i+1}")) for it in items[:8]]
            for it in items[:8]:
                sub = it.get("items", [])
                row_cells = []
                if isinstance(sub, list):
                    for s in (sub if columns else sub[:5]):
                        if isinstance(s, dict):
                            row_cells.append(MatrixCell(
                                status=s.get("status", "no"),
                                note=s.get("note", ""),
                            ))
                        else:
                            row_cells.append(MatrixCell(status="yes", note=str(s)))
                elif isinstance(sub, dict):
                    for k in columns[:5]:
                        v = sub.get(k, {})
                        if isinstance(v, dict):
                            row_cells.append(MatrixCell(status=v.get("status", "no"), note=v.get("note", "")))
                        else:
                            row_cells.append(MatrixCell(status="yes" if v else "no", note=""))
                if not row_cells:
                    row_cells = [MatrixCell() for _ in columns]
                cells.append(row_cells)

        if not rows:
            tbs = slide_data.get("text_blocks", [])
            for tb in tbs[:4]:
                c = tb.get("content", tb.get("text", ""))
                if c:
                    rows.append(c[:20])
            if not rows:
                rows = ["维度"]
            if not columns:
                columns = ["当前", "规划"]
            cells = [[MatrixCell() for _ in columns] for _ in rows]

        while len(cells) < len(rows):
            cells.append([MatrixCell() for _ in columns])

        return CapabilityMatrixContent(
            title=slide_data.get("takeaway_message", ""),
            columns=columns,
            rows=rows,
            cells=cells,
        )

    def build_html(
        self,
        content: CapabilityMatrixContent,
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
        n_cols = len(content.columns)
        n_rows = len(content.rows)
        table_w = 880
        label_w = 180
        cell_w = (table_w - label_w) // max(n_cols, 1)

        # Header row
        header_html = (
            f'<th style="width:{label_w}px; background:{primary}; color:#FFF; '
            f'font-size:12px; padding:8px; text-align:center; border:1px solid {primary};">维度</th>\n'
        )
        for col in content.columns:
            header_html += (
                f'<th style="width:{cell_w}px; background:{primary}; color:#FFF; '
                f'font-size:12px; padding:8px; text-align:center; '
                f'border:1px solid {primary};">{_html.escape(col)}</th>\n'
            )

        # Data rows
        rows_html = ""
        for r_idx, row_name in enumerate(content.rows):
            bg_color = "#FFFFFF" if r_idx % 2 == 0 else bg
            row_cells = content.cells[r_idx] if r_idx < len(content.cells) else []
            rows_html += f'<tr>\n'
            rows_html += (
                f'  <td style="background:{bg_color}; font-size:11px; font-weight:bold; '
                f'color:{text_color}; padding:6px 8px; border:1px solid {border}; '
                f'white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
                f'{_html.escape(row_name)}</td>\n'
            )
            for c_idx in range(n_cols):
                cell = row_cells[c_idx] if c_idx < len(row_cells) else MatrixCell()
                icon = _STATUS_ICONS.get(cell.status, "&#9675;")
                color = _STATUS_COLORS.get(cell.status, muted)
                note_e = _html.escape(cell.note) if cell.note else ""
                note_html = f'<br><span style="font-size:9px;color:{muted}">{note_e}</span>' if note_e else ""
                rows_html += (
                    f'  <td style="background:{bg_color}; text-align:center; '
                    f'padding:6px; border:1px solid {border}; font-size:11px;">'
                    f'<span style="color:{color}; font-size:16px;">{icon}</span>'
                    f'{note_html}'
                    f'</td>\n'
                )
            rows_html += '</tr>\n'

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
            f'<div style="position:absolute; left:40px; top:76px; width:{table_w}px; '
            f'max-height:420px; overflow:auto;">\n'
            f'<table style="border-collapse:collapse; width:{table_w}px;">\n'
            f'<tr>{header_html}</tr>\n'
            f'{rows_html}'
            f'</table>\n</div>\n'
            '</body></html>'
        )

    def prompt_fragment(self) -> str:
        return (
            "能力矩阵：横轴2-5列（阶段/方案），纵轴2-8行（能力维度），"
            "单元格含状态（yes/no/partial/planned）和可选备注。"
            "visual_block.items[].title=维度名，items[]=各列状态。"
        )
