"""
slide_templates.py — Pre-designed slide templates for HTMLDesignAgent.

Instead of LLM generating free HTML, the LLM picks a template_id and fills
structured slots. Python renders the final HTML from pre-validated templates.

Canvas: 960 × 540 px (16:9, 96 DPI)
Content area: left:40px, top:72px (below title bar), right:40px, above footer
Chrome: 6px accent top bar + 24px primary footer (always injected by template)
"""

from __future__ import annotations

import html as _html
from typing import Any

# --------------------------------------------------------------------------- #
# Template strings — placeholders use <<SLOT_NAME>> to avoid CSS {} conflicts
# --------------------------------------------------------------------------- #

_T_CONTENT_BULLETS = """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:960px; height:540px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:#FFFFFF; position:relative; overflow:hidden;">

<div style="position:absolute; top:0; left:0; width:960px; height:6px; background-color:<<ACCENT>>;"></div>
<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; background-color:<<PRIMARY>>;">
  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;"><<FOOTER>></p>
</div>

<div style="position:absolute; left:24px; top:28px; width:4px; height:36px; background-color:<<PRIMARY>>;"></div>
<h2 style="position:absolute; left:40px; top:22px; width:<<TITLE_W>>px; font-size:16px; color:<<PRIMARY>>; font-weight:bold; line-height:1.35; overflow:hidden; height:44px;"><<TITLE>></h2>

<div style="position:absolute; left:40px; top:76px; width:<<CONTENT_W>>px; height:420px; overflow:hidden;">
<<BULLETS_HTML>>
</div>

<<CHART_PLACEHOLDER>>

</body>
</html>"""

_T_CONTENT_TWO_COLUMN = """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:960px; height:540px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:#FFFFFF; position:relative; overflow:hidden;">

<div style="position:absolute; top:0; left:0; width:960px; height:6px; background-color:<<ACCENT>>;"></div>
<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; background-color:<<PRIMARY>>;">
  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;"><<FOOTER>></p>
</div>

<div style="position:absolute; left:24px; top:28px; width:4px; height:36px; background-color:<<PRIMARY>>;"></div>
<h2 style="position:absolute; left:40px; top:22px; width:880px; font-size:16px; color:<<PRIMARY>>; font-weight:bold; line-height:1.35; overflow:hidden; height:44px;"><<TITLE>></h2>

<div style="position:absolute; left:480px; top:72px; width:1px; height:434px; background-color:#E0E0E0;"></div>

<div style="position:absolute; left:40px; top:76px; width:420px; height:28px; background-color:<<BG>>;">
  <p style="font-size:12px; font-weight:bold; color:<<PRIMARY>>; margin:5px 8px;"><<LEFT_LABEL>></p>
</div>
<div style="position:absolute; left:40px; top:112px; width:420px; height:398px; overflow:hidden;">
<<LEFT_BULLETS_HTML>>
</div>

<div style="position:absolute; left:496px; top:76px; width:420px; height:28px; background-color:<<BG>>;">
  <p style="font-size:12px; font-weight:bold; color:<<PRIMARY>>; margin:5px 8px;"><<RIGHT_LABEL>></p>
</div>
<div style="position:absolute; left:496px; top:112px; width:420px; height:398px; overflow:hidden;">
<<RIGHT_BULLETS_HTML>>
</div>

</body>
</html>"""

_T_CONTENT_KEY_METRICS = """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:960px; height:540px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:#FFFFFF; position:relative; overflow:hidden;">

<div style="position:absolute; top:0; left:0; width:960px; height:6px; background-color:<<ACCENT>>;"></div>
<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; background-color:<<PRIMARY>>;">
  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;"><<FOOTER>></p>
</div>

<div style="position:absolute; left:24px; top:28px; width:4px; height:36px; background-color:<<PRIMARY>>;"></div>
<h2 style="position:absolute; left:40px; top:22px; width:880px; font-size:16px; color:<<PRIMARY>>; font-weight:bold; line-height:1.35; overflow:hidden; height:44px;"><<TITLE>></h2>

<<METRIC_BOXES_HTML>>

<div style="position:absolute; left:40px; top:400px; width:880px; height:110px; overflow:hidden;">
<<SUB_BULLETS_HTML>>
</div>

</body>
</html>"""

_T_CHART_FOCUS = """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:960px; height:540px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:#FFFFFF; position:relative; overflow:hidden;">

<div style="position:absolute; top:0; left:0; width:960px; height:6px; background-color:<<ACCENT>>;"></div>
<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; background-color:<<PRIMARY>>;">
  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;"><<FOOTER>></p>
</div>

<div style="position:absolute; left:24px; top:28px; width:4px; height:36px; background-color:<<PRIMARY>>;"></div>
<h2 style="position:absolute; left:40px; top:22px; width:880px; font-size:16px; color:<<PRIMARY>>; font-weight:bold; line-height:1.35; overflow:hidden; height:44px;"><<TITLE>></h2>

<div class="placeholder" id="chart-0" style="position:absolute; left:360px; top:76px; width:556px; height:420px;"></div>

<div style="position:absolute; left:40px; top:76px; width:300px; height:420px; overflow:hidden;">
<<ANNOTATIONS_HTML>>
</div>

</body>
</html>"""

_T_QUOTE_HIGHLIGHT = """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:960px; height:540px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:#FFFFFF; position:relative; overflow:hidden;">

<div style="position:absolute; top:0; left:0; width:960px; height:6px; background-color:<<ACCENT>>;"></div>
<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; background-color:<<PRIMARY>>;">
  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;"><<FOOTER>></p>
</div>

<div style="position:absolute; left:24px; top:28px; width:4px; height:36px; background-color:<<PRIMARY>>;"></div>
<h2 style="position:absolute; left:40px; top:22px; width:880px; font-size:16px; color:<<PRIMARY>>; font-weight:bold; line-height:1.35; overflow:hidden; height:44px;"><<TITLE>></h2>

<div style="position:absolute; left:40px; top:76px; width:880px; height:108px; background-color:<<BG>>;">
  <div style="position:absolute; left:0; top:0; width:6px; height:108px; background-color:<<ACCENT>>;"></div>
  <p style="position:absolute; left:20px; top:16px; width:844px; font-size:17px; color:<<PRIMARY>>; font-weight:bold; line-height:1.55; overflow:hidden;"><<QUOTE_TEXT>></p>
</div>

<div style="position:absolute; left:40px; top:198px; width:880px; height:300px; overflow:hidden;">
<<SUB_BULLETS_HTML>>
</div>

</body>
</html>"""

_T_ICON_GRID = """\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:960px; height:540px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:#FFFFFF; position:relative; overflow:hidden;">

<div style="position:absolute; top:0; left:0; width:960px; height:6px; background-color:<<ACCENT>>;"></div>
<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; background-color:<<PRIMARY>>;">
  <p style="font-size:9px; color:#FFFFFF; margin:4px 24px;"><<FOOTER>></p>
</div>

<div style="position:absolute; left:24px; top:28px; width:4px; height:36px; background-color:<<PRIMARY>>;"></div>
<h2 style="position:absolute; left:40px; top:22px; width:880px; font-size:16px; color:<<PRIMARY>>; font-weight:bold; line-height:1.35; overflow:hidden; height:44px;"><<TITLE>></h2>

<<GRID_ITEMS_HTML>>

</body>
</html>"""

TEMPLATES: dict[str, str] = {
    "content_bullets": _T_CONTENT_BULLETS,
    "content_two_column": _T_CONTENT_TWO_COLUMN,
    "content_key_metrics": _T_CONTENT_KEY_METRICS,
    "chart_focus": _T_CHART_FOCUS,
    "quote_highlight": _T_QUOTE_HIGHLIGHT,
    "icon_grid": _T_ICON_GRID,
}

# Schema used to generate the LLM system prompt
TEMPLATE_SCHEMAS: dict[str, dict] = {
    "content_bullets": {
        "description": "标准要点列表，适合3-5个并列论据/证据。",
        "required_slots": {
            "title": "str — 核心论点句（来自 takeaway_message）",
            "bullets": "list[str] — 要点列表，最多5条，每条≤40字",
        },
        "optional_slots": {
            "has_chart": "bool — true 则右侧留图表占位（默认 false）",
        },
    },
    "content_two_column": {
        "description": "两栏对比/并列，适合 before/after、方案A vs B、两维度分析。",
        "required_slots": {
            "title": "str — 核心论点句",
            "left_label": "str — 左栏标题（≤12字）",
            "left_bullets": "list[str] — 左栏要点，最多4条",
            "right_label": "str — 右栏标题（≤12字）",
            "right_bullets": "list[str] — 右栏要点，最多4条",
        },
    },
    "content_key_metrics": {
        "description": "关键数据指标，适合3-4个核心数字，强调数据冲击力。",
        "required_slots": {
            "title": "str — 核心论点句",
            "metrics": 'list[{label:str, value:str, unit:str, note:str}] — 指标，最多4个',
        },
        "optional_slots": {
            "sub_bullets": "list[str] — 数据下方补充说明，最多3条",
        },
    },
    "chart_focus": {
        "description": "图表主页，适合趋势/分布/对比图，文字辅助标注关键发现。需要 chart_suggestion 数据。",
        "required_slots": {
            "title": "str — 核心论点句",
            "annotations": "list[str] — 图表关键发现标注，最多4条，每条≤35字",
        },
    },
    "quote_highlight": {
        "description": "核心结论强调页，适合最重要的一句话 + 支撑论点。",
        "required_slots": {
            "title": "str — 页面标题",
            "quote_text": "str — 需强调的核心句（≤60字）",
            "sub_bullets": "list[str] — 支撑论点，最多4条",
        },
    },
    "icon_grid": {
        "description": "框架/原则网格，适合3-6个并列概念，每个有图标+标题+描述。",
        "required_slots": {
            "title": "str — 核心论点句",
            "items": "list[{icon:str, title:str, desc:str}] — 网格项3-6个，icon为单个emoji",
        },
    },
}


# --------------------------------------------------------------------------- #
# Renderer
# --------------------------------------------------------------------------- #

def render_template(
    template_id: str,
    slots: dict[str, Any],
    theme_colors: dict[str, str],
    page_number: int = 1,
    total_slides: int = 1,
) -> str:
    """
    Fill template <<SLOT_NAME>> placeholders with slot values and theme colors.
    Returns a complete HTML document string ready for html2pptx.js.
    """
    if template_id not in TEMPLATES:
        template_id = "content_bullets"

    tmpl = TEMPLATES[template_id]
    primary = theme_colors.get("primary", "#003D6E")
    accent = theme_colors.get("accent", "#FF6B35")
    bg = theme_colors.get("bg", "#EEF4FA")
    text_color = theme_colors.get("text", "#2D3436")
    muted = theme_colors.get("muted", "#636E72")
    footer = _html.escape(f"第 {page_number} 页 / 共 {total_slides} 页")
    title = _html.escape(str(slots.get("title", "")))

    result = tmpl
    result = result.replace("<<PRIMARY>>", primary)
    result = result.replace("<<ACCENT>>", accent)
    result = result.replace("<<BG>>", bg)
    result = result.replace("<<FOOTER>>", footer)
    result = result.replace("<<TITLE>>", title)

    if template_id == "content_bullets":
        has_chart = bool(slots.get("has_chart", False))
        title_w = 440 if has_chart else 880
        content_w = 436 if has_chart else 880
        bullets_html = _render_bullets(slots.get("bullets", []), text_color, primary)
        chart_ph = (
            '<div class="placeholder" id="chart-0" '
            'style="position:absolute; left:512px; top:76px; width:404px; height:420px;"></div>'
            if has_chart else ""
        )
        result = result.replace("<<TITLE_W>>", str(title_w))
        result = result.replace("<<CONTENT_W>>", str(content_w))
        result = result.replace("<<BULLETS_HTML>>", bullets_html)
        result = result.replace("<<CHART_PLACEHOLDER>>", chart_ph)

    elif template_id == "content_two_column":
        result = result.replace("<<LEFT_LABEL>>", _html.escape(str(slots.get("left_label", ""))))
        result = result.replace("<<RIGHT_LABEL>>", _html.escape(str(slots.get("right_label", ""))))
        result = result.replace("<<LEFT_BULLETS_HTML>>",
                                _render_bullets(slots.get("left_bullets", []), text_color, primary))
        result = result.replace("<<RIGHT_BULLETS_HTML>>",
                                _render_bullets(slots.get("right_bullets", []), text_color, primary))

    elif template_id == "content_key_metrics":
        metrics = slots.get("metrics", [])
        result = result.replace("<<METRIC_BOXES_HTML>>",
                                _render_metrics(metrics, primary, accent, bg, text_color, muted))
        sub = slots.get("sub_bullets", [])
        result = result.replace("<<SUB_BULLETS_HTML>>",
                                _render_bullets(sub, muted, primary, font_size=11) if sub else "")

    elif template_id == "chart_focus":
        result = result.replace("<<ANNOTATIONS_HTML>>",
                                _render_annotations(slots.get("annotations", []), primary, accent, muted))

    elif template_id == "quote_highlight":
        result = result.replace("<<QUOTE_TEXT>>", _html.escape(str(slots.get("quote_text", ""))))
        result = result.replace("<<SUB_BULLETS_HTML>>",
                                _render_bullets(slots.get("sub_bullets", []), text_color, primary))

    elif template_id == "icon_grid":
        result = result.replace("<<GRID_ITEMS_HTML>>",
                                _render_icon_grid(slots.get("items", []), primary, accent, bg, text_color))

    return result


# --------------------------------------------------------------------------- #
# Private HTML builders
# --------------------------------------------------------------------------- #

def _render_bullets(bullets: list, text_color: str, primary: str, font_size: int = 13) -> str:
    parts = []
    for b in bullets[:6]:
        text = _html.escape(str(b))
        parts.append(
            f'<p style="font-size:{font_size}px; color:{text_color}; margin-bottom:14px; line-height:1.55;">'
            f'<span style="color:{primary}; font-weight:bold; margin-right:8px;">■</span>{text}</p>'
        )
    return "\n".join(parts)


def _render_metrics(
    metrics: list,
    primary: str,
    accent: str,
    bg: str,
    text_color: str,
    muted: str,
) -> str:
    n = min(len(metrics), 4)
    if n == 0:
        return ""
    if n <= 3:
        box_w = 260
        gap = (880 - n * box_w) // (n + 1)
        starts = [40 + gap + i * (box_w + gap) for i in range(n)]
    else:
        box_w = 200
        gap = (880 - n * box_w) // (n + 1)
        starts = [40 + gap + i * (box_w + gap) for i in range(n)]

    box_top = 86
    box_h = 260

    parts = []
    for i, m in enumerate(metrics[:4]):
        label = _html.escape(str(m.get("label", "")))
        value = _html.escape(str(m.get("value", "")))
        unit = _html.escape(str(m.get("unit", "")))
        note = _html.escape(str(m.get("note", "")))
        left = starts[i]
        parts.append(
            f'<div style="position:absolute; left:{left}px; top:{box_top}px; width:{box_w}px; height:{box_h}px; background-color:{bg};">'
            f'<div style="position:absolute; top:0; left:0; width:{box_w}px; height:4px; background-color:{accent};"></div>'
            f'<p style="position:absolute; left:14px; top:16px; font-size:12px; color:{muted};">{label}</p>'
            f'<p style="position:absolute; left:14px; top:46px; font-size:38px; color:{primary}; font-weight:bold; line-height:1;">{value}'
            f'<span style="font-size:15px; color:{muted}; margin-left:4px;">{unit}</span></p>'
            f'<p style="position:absolute; left:14px; top:114px; width:{box_w - 28}px; font-size:11px; color:{muted}; line-height:1.45;">{note}</p>'
            f'</div>'
        )
    return "\n".join(parts)


def _render_annotations(annotations: list, primary: str, accent: str, muted: str) -> str:
    parts = []
    for i, ann in enumerate(annotations[:4]):
        text = _html.escape(str(ann))
        top = i * 96
        parts.append(
            f'<div style="position:absolute; left:0; top:{top}px; width:300px; height:86px;">'
            f'<div style="position:absolute; left:0; top:0; width:4px; height:70px; background-color:{accent};"></div>'
            f'<p style="position:absolute; left:12px; top:0; width:280px; font-size:12px; color:{primary}; line-height:1.55;">{text}</p>'
            f'</div>'
        )
    return "\n".join(parts)


def _render_icon_grid(items: list, primary: str, accent: str, bg: str, text_color: str) -> str:
    n = min(len(items), 6)
    if n == 0:
        return ""
    if n <= 3:
        cols, rows, box_w, box_h, top_start = n, 1, 260, 310, 84
    elif n == 4:
        cols, rows, box_w, box_h, top_start = 2, 2, 410, 196, 80
    else:
        cols, rows, box_w, box_h, top_start = 3, 2, 263, 196, 80

    gap_x = (880 - cols * box_w) // (cols + 1)

    parts = []
    for i, item in enumerate(items[:n]):
        col = i % cols
        row = i // cols
        icon = str(item.get("icon", "●"))
        item_title = _html.escape(str(item.get("title", "")))
        desc = _html.escape(str(item.get("desc", "")))
        left = 40 + gap_x + col * (box_w + gap_x)
        top = top_start + row * (box_h + 10)
        parts.append(
            f'<div style="position:absolute; left:{left}px; top:{top}px; width:{box_w}px; height:{box_h}px; background-color:{bg};">'
            f'<div style="position:absolute; top:0; left:0; width:{box_w}px; height:3px; background-color:{primary};"></div>'
            f'<p style="position:absolute; left:12px; top:10px; font-size:22px;">{icon}</p>'
            f'<p style="position:absolute; left:12px; top:46px; font-size:13px; color:{primary}; font-weight:bold;">{item_title}</p>'
            f'<p style="position:absolute; left:12px; top:72px; width:{box_w - 24}px; font-size:11px; color:{text_color}; line-height:1.45;">{desc}</p>'
            f'</div>'
        )
    return "\n".join(parts)
