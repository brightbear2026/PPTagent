"""
DEPRECATED: Legacy slide templates. Referenced only by fallback builder.
Primary path uses LLM-generated HTML.

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

_T_ARCHITECTURE_STACK = """\
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

<<STACK_LAYERS_HTML>>

</body>
</html>"""

_T_TIMELINE_HORIZONTAL = """\
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

<<TIMELINE_ITEMS_HTML>>

</body>
</html>"""

_T_QUADRANT_MATRIX = """\
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

<<QUADRANT_CELLS_HTML>>

</body>
</html>"""

_T_ROLE_COLUMNS = """\
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

<<ROLE_COLUMNS_HTML>>

</body>
</html>"""

TEMPLATES: dict[str, str] = {
    "content_bullets": _T_CONTENT_BULLETS,
    "content_two_column": _T_CONTENT_TWO_COLUMN,
    "content_key_metrics": _T_CONTENT_KEY_METRICS,
    "chart_focus": _T_CHART_FOCUS,
    "quote_highlight": _T_QUOTE_HIGHLIGHT,
    "icon_grid": _T_ICON_GRID,
    "architecture_stack": _T_ARCHITECTURE_STACK,
    "timeline_horizontal": _T_TIMELINE_HORIZONTAL,
    "quadrant_matrix": _T_QUADRANT_MATRIX,
    "role_columns": _T_ROLE_COLUMNS,
    "hero_splash": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="width:960px;height:540px;margin:0;padding:0;background:<<BG>>;font-family:'Microsoft YaHei',Arial,sans-serif;overflow:hidden;box-sizing:border-box;">
  <p style="position:absolute;left:130px;top:130px;width:700px;height:60px;color:<<MUTED>>;font-size:18px;text-align:center;line-height:1.4;margin:0;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;"><<HEADLINE>></p>
  <h1 style="position:absolute;left:130px;top:210px;width:700px;height:90px;color:<<PRIMARY>>;font-size:72px;font-weight:700;text-align:center;line-height:1.1;letter-spacing:-2px;margin:0;"><<BIG_NUMBER>></h1>
  <p style="position:absolute;left:130px;top:320px;width:700px;height:30px;color:<<ACCENT>>;font-size:16px;font-weight:500;text-align:center;margin:0;"><<NUMBER_CAPTION>></p>
  <p style="position:absolute;left:180px;top:370px;width:600px;height:50px;color:<<MUTED>>;font-size:14px;text-align:center;line-height:1.5;margin:0;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;"><<SUBTITLE>></p>
  <div style="position:absolute;bottom:16px;right:32px;color:<<MUTED>>;font-size:10px;opacity:0.5;"><p style="color:<<MUTED>>;font-size:10px;margin:0;">P<<PAGE_NUMBER>>/<<TOTAL_SLIDES>></p></div>
</body></html>""",
    # ── IT diagram templates ────────────────────────────────────────────
    "tech_stack_layers": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="width:960px;height:540px;margin:0;padding:0;background:<<BG>>;font-family:'Microsoft YaHei',Arial,sans-serif;overflow:hidden;box-sizing:border-box;">
<div style="position:absolute;left:0;top:0;width:960px;height:6px;background:<<ACCENT>>;"></div>
<div style="position:absolute;left:40px;top:20px;width:4px;height:24px;background:<<PRIMARY>>;"></div>
<p style="position:absolute;left:52px;top:18px;font-size:16px;font-weight:bold;color:<<TEXT_COLOR>>;"><<TITLE>></p>
<div style="position:absolute;left:40px;top:52px;width:880px;"><<STACK_LAYERS_HTML>></div>
<div style="position:absolute;left:0;bottom:0;width:960px;height:24px;background:<<PRIMARY>>;"><p style="color:#FFFFFF;font-size:9px;margin:5px 40px;opacity:0.8;"><<FOOTER>></p></div>
</body></html>""",
    "component_network": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="width:960px;height:540px;margin:0;padding:0;background:<<BG>>;font-family:'Microsoft YaHei',Arial,sans-serif;overflow:hidden;box-sizing:border-box;">
<div style="position:absolute;left:0;top:0;width:960px;height:6px;background:<<ACCENT>>;"></div>
<div style="position:absolute;left:40px;top:20px;width:4px;height:24px;background:<<PRIMARY>>;"></div>
<p style="position:absolute;left:52px;top:18px;font-size:16px;font-weight:bold;color:<<TEXT_COLOR>>;"><<TITLE>></p>
<div style="position:absolute;left:40px;top:56px;width:880px;height:440px;"><<COMPONENT_GROUPS_HTML>></div>
<div style="position:absolute;left:0;bottom:0;width:960px;height:24px;background:<<PRIMARY>>;"><p style="color:#FFFFFF;font-size:9px;margin:5px 40px;opacity:0.8;"><<FOOTER>></p></div>
</body></html>""",
    "data_pipeline": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="width:960px;height:540px;margin:0;padding:0;background:<<BG>>;font-family:'Microsoft YaHei',Arial,sans-serif;overflow:hidden;box-sizing:border-box;">
<div style="position:absolute;left:0;top:0;width:960px;height:6px;background:<<ACCENT>>;"></div>
<div style="position:absolute;left:40px;top:20px;width:4px;height:24px;background:<<PRIMARY>>;"></div>
<p style="position:absolute;left:52px;top:18px;font-size:16px;font-weight:bold;color:<<TEXT_COLOR>>;"><<TITLE>></p>
<div style="position:absolute;left:40px;top:60px;width:880px;height:420px;"><<PIPELINE_STAGES_HTML>></div>
<div style="position:absolute;left:0;bottom:0;width:960px;height:24px;background:<<PRIMARY>>;"><p style="color:#FFFFFF;font-size:9px;margin:5px 40px;opacity:0.8;"><<FOOTER>></p></div>
</body></html>""",
    "tech_comparison": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="width:960px;height:540px;margin:0;padding:0;background:<<BG>>;font-family:'Microsoft YaHei',Arial,sans-serif;overflow:hidden;box-sizing:border-box;">
<div style="position:absolute;left:0;top:0;width:960px;height:6px;background:<<ACCENT>>;"></div>
<div style="position:absolute;left:40px;top:20px;width:4px;height:24px;background:<<PRIMARY>>;"></div>
<p style="position:absolute;left:52px;top:18px;font-size:16px;font-weight:bold;color:<<TEXT_COLOR>>;"><<TITLE>></p>
<div style="position:absolute;left:40px;top:56px;width:880px;"><<MATRIX_TABLE_HTML>></div>
<div style="position:absolute;left:0;bottom:0;width:960px;height:24px;background:<<PRIMARY>>;"><p style="color:#FFFFFF;font-size:9px;margin:5px 40px;opacity:0.8;"><<FOOTER>></p></div>
</body></html>""",
}

# Schema used to generate the LLM system prompt
TEMPLATE_SCHEMAS: dict[str, dict] = {
    "content_bullets": {
        "description": "标准要点列表，适合4-8个并列论据/证据。",
        "required_slots": {
            "title": "str — 核心论点句（来自 takeaway_message）",
            "bullets": "list[str] — 要点列表，最多8条，每条≤80字",
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
            "left_bullets": "list[str] — 左栏要点，最多6条",
            "right_label": "str — 右栏标题（≤12字）",
            "right_bullets": "list[str] — 右栏要点，最多6条",
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
            "annotations": "list[str] — 图表关键发现标注，最多6条，每条≤80字",
        },
    },
    "quote_highlight": {
        "description": "核心结论强调页，适合最重要的一句话 + 支撑论点。",
        "required_slots": {
            "title": "str — 页面标题",
            "quote_text": "str — 需强调的核心句（≤120字）",
            "sub_bullets": "list[str] — 支撑论点，最多5条",
        },
    },
    "icon_grid": {
        "description": "框架/原则网格，适合3-6个并列概念，每个有图标+标题+描述。",
        "required_slots": {
            "title": "str — 核心论点句",
            "items": "list[{icon:str, title:str, desc:str}] — 网格项3-6个，icon为单个emoji",
        },
    },
    "architecture_stack": {
        "description": "N层堆叠架构图，适合基础设施→平台→应用等分层结构，从下到上堆叠。",
        "required_slots": {
            "title": "str — 核心论点句",
            "layers": "list[{name:str, desc:str}] — 堆叠层2-6层，从底层到顶层排列",
        },
    },
    "timeline_horizontal": {
        "description": "横向时间线/路线图，适合多阶段计划、里程碑节点。",
        "required_slots": {
            "title": "str — 核心论点句",
            "phases": "list[{label:str, title:str, desc:str}] — 阶段2-6个，label为时间标签如'90天'",
        },
    },
    "quadrant_matrix": {
        "description": "2×2象限矩阵，适合按两个维度分类的四种状态/策略。",
        "required_slots": {
            "title": "str — 核心论点句",
            "x_label": "str — 横轴标签（≤10字）",
            "y_label": "str — 纵轴标签（≤10字）",
            "cells": "list[{label:str, items:list[str]}] — 4个格子，按 左下/右下/左上/右上 顺序",
        },
    },
    "role_columns": {
        "description": "3-4列角色/对象对比，每列展示一个角色的特征、职责、能力。",
        "required_slots": {
            "title": "str — 核心论点句",
            "roles": "list[{name:str, subtitle:str, bullets:list[str]}] — 角色3-4个，bullets最多4条",
        },
    },
    "hero_splash": {
        "description": "核心论点页，超大数字+极简文字+大量留白，用于hero页。",
        "required_slots": {
            "headline": "str — 核心论点一行（takeaway_message）",
            "big_number": "str — 最震撼的数字（如'15.6亿'、'+32%'）",
            "number_caption": "str — 数字说明（如'同比增长'）",
            "subtitle": "str — 一句支撑论点（≤40字）",
        },
    },
    "tech_stack_layers": {
        "description": "技术分层架构图，3-7层堆叠，使用IT语义色板。",
        "required_slots": {
            "title": "str — 核心论点句",
            "layers": "list[{name:str, desc:str, color:str}] — 堆叠层3-7层，color可选（#hex）",
        },
    },
    "component_network": {
        "description": "组件/微服务拓扑图，分组容器+简化连线，≤6节点。",
        "required_slots": {
            "title": "str — 核心论点句",
            "groups": "list[{name:str, components:list[str]}] — 服务分组2-4组",
        },
        "optional_slots": {
            "connections": "list[{from:str, to:str, label:str}] — 组间调用关系",
        },
    },
    "data_pipeline": {
        "description": "数据流管线图，水平pipeline，source→transform→store→consume。",
        "required_slots": {
            "title": "str — 核心论点句",
            "stages": "list[{label:str, type:str, desc:str}] — 管线阶段3-8个，type: source/transform/store/consume",
        },
        "optional_slots": {
            "flows": "list[{from:str, to:str, label:str}] — 数据流标注",
        },
    },
    "tech_comparison": {
        "description": "技术选型矩阵，行=类别，列=选项，选中项高亮。",
        "required_slots": {
            "title": "str — 核心论点句",
            "categories": "list[{name:str, options:list[{name:str, selected:bool}]}] — 类别3-6个",
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
    page_weight: str = "",
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
    result = result.replace("<<MUTED>>", muted)
    result = result.replace("<<TEXT_COLOR>>", text_color)
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

    elif template_id == "architecture_stack":
        result = result.replace("<<STACK_LAYERS_HTML>>",
                                _render_stack_layers(slots.get("layers", []), primary, accent, bg, text_color, muted))

    elif template_id == "timeline_horizontal":
        result = result.replace("<<TIMELINE_ITEMS_HTML>>",
                                _render_timeline(slots.get("phases", []), primary, accent, bg, text_color, muted))

    elif template_id == "quadrant_matrix":
        result = result.replace("<<QUADRANT_CELLS_HTML>>",
                                _render_quadrant(slots.get("cells", []),
                                                 slots.get("x_label", ""), slots.get("y_label", ""),
                                                 primary, accent, bg, text_color, muted))

    elif template_id == "role_columns":
        result = result.replace("<<ROLE_COLUMNS_HTML>>",
                                _render_role_columns(slots.get("roles", []), primary, accent, bg, text_color, muted))

    elif template_id == "hero_splash":
        result = result.replace("<<HEADLINE>>", _html.escape(str(slots.get("headline", ""))))
        result = result.replace("<<BIG_NUMBER>>", _html.escape(str(slots.get("big_number", ""))))
        result = result.replace("<<NUMBER_CAPTION>>", _html.escape(str(slots.get("number_caption", ""))))
        result = result.replace("<<SUBTITLE>>", _html.escape(str(slots.get("subtitle", ""))))
        result = result.replace("<<PAGE_NUMBER>>", str(page_number))
        result = result.replace("<<TOTAL_SLIDES>>", str(total_slides))

    elif template_id == "tech_stack_layers":
        result = result.replace("<<STACK_LAYERS_HTML>>",
                                _render_stack_layers(slots.get("layers", []), primary, accent, bg, text_color, muted))

    elif template_id == "component_network":
        result = result.replace("<<COMPONENT_GROUPS_HTML>>",
                                _render_component_groups(slots.get("groups", []),
                                                         slots.get("connections", []),
                                                         primary, accent, bg, text_color, muted))

    elif template_id == "data_pipeline":
        result = result.replace("<<PIPELINE_STAGES_HTML>>",
                                _render_pipeline_stages(slots.get("stages", []),
                                                        slots.get("flows", []),
                                                        primary, accent, bg, text_color, muted))

    elif template_id == "tech_comparison":
        result = result.replace("<<MATRIX_TABLE_HTML>>",
                                _render_tech_matrix(slots.get("categories", []),
                                                    primary, accent, bg, text_color, muted))

    return result


# --------------------------------------------------------------------------- #
# Private HTML builders
# --------------------------------------------------------------------------- #

def _render_bullets(bullets: list, text_color: str, primary: str, font_size: int = 13) -> str:
    parts = []
    for b in bullets[:8]:
        text = _html.escape(str(b))
        parts.append(
            f'<p style="font-size:{font_size}px; color:{text_color}; margin-bottom:14px; line-height:1.55;">'
            f'<span style="color:{primary}; font-weight:bold; margin-right:8px;">■</span>{text}</p>'
        )
    return "\n".join(parts)


def _weighted_len(text: str) -> float:
    """Weighted character length: CJK/full-width=1.0, digit=0.6, other=0.75."""
    total = 0.0
    for ch in text:
        if '一' <= ch <= '鿿' or '　' <= ch <= '〿' or '＀' <= ch <= '￯':
            total += 1.0
        elif ch.isdigit():
            total += 0.6
        else:
            total += 0.75
    return total


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

    # Adaptive font-size based on column count and value length
    value_font = {1: 56, 2: 48, 3: 38, 4: 30}.get(n, 38)
    value_top = {1: 36, 2: 40, 3: 46, 4: 50}.get(n, 46)
    note_top = {1: 108, 2: 110, 3: 114, 4: 100}.get(n, 114)

    parts = []
    for i, m in enumerate(metrics[:4]):
        label = _html.escape(str(m.get("label", "")))
        value = _html.escape(str(m.get("value", "")))
        unit = _html.escape(str(m.get("unit", "")))
        note = _html.escape(str(m.get("note", "")))
        left = starts[i]
        # Shrink font based on weighted character width (CJK wider than digits)
        raw_text = str(m.get("value", "")) + str(m.get("unit", ""))
        w_len = _weighted_len(raw_text)
        max_font_by_width = int((box_w - 28) / max(w_len, 1) * 0.95)
        value_font_cur = min(value_font, max_font_by_width)
        value_font_cur = max(value_font_cur, 18)  # floor protection
        parts.append(
            f'<div style="position:absolute; left:{left}px; top:{box_top}px; width:{box_w}px; height:{box_h}px; background-color:{bg};">'
            f'<div style="position:absolute; top:0; left:0; width:{box_w}px; height:4px; background-color:{accent};"></div>'
            f'<p style="position:absolute; left:14px; top:16px; font-size:12px; color:{muted};">{label}</p>'
            f'<p style="position:absolute; left:14px; top:{value_top}px; font-size:{value_font_cur}px; color:{primary}; font-weight:bold; line-height:1; white-space:nowrap;">{value}'
            f'<span style="font-size:15px; color:{muted}; margin-left:4px;">{unit}</span></p>'
            f'<p style="position:absolute; left:14px; top:{note_top}px; width:{box_w - 28}px; font-size:11px; color:{muted}; line-height:1.45;">{note}</p>'
            f'</div>'
        )
    return "\n".join(parts)


def _render_annotations(annotations: list, primary: str, accent: str, muted: str) -> str:
    parts = []
    for i, ann in enumerate(annotations[:6]):
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


def _render_stack_layers(
    layers: list, primary: str, accent: str, bg: str, text_color: str, muted: str,
) -> str:
    """Render N-layer stack (bottom to top)."""
    n = min(len(layers), 6)
    if n == 0:
        return ""
    layer_h = min(80, (420 - (n - 1) * 6) // n)
    total_h = n * layer_h + (n - 1) * 6
    top_start = 76 + (430 - total_h) // 2
    colors = [primary, accent, bg, _lighten(primary, 0.6), _lighten(primary, 0.8)][:n]
    text_colors = ["#FFFFFF", "#FFFFFF", text_color, primary, primary][:n]
    parts = []
    for i, layer in enumerate(layers[:n]):
        idx = n - 1 - i  # reverse: first in list = bottom of stack
        name = _html.escape(str(layer.get("name", f"Layer {i+1}")))
        desc = _html.escape(str(layer.get("desc", "")))
        top = top_start + idx * (layer_h + 6)
        c = colors[i]
        tc = text_colors[i]
        parts.append(
            f'<div style="position:absolute; left:60px; top:{top}px; width:840px; height:{layer_h}px; background-color:{c}; border-radius:3px;">'
            f'<p style="position:absolute; left:16px; top:{max(4, (layer_h-20)//2)}px; font-size:14px; color:{tc}; font-weight:bold;">{name}</p>'
            f'<p style="position:absolute; left:16px; top:{max(4, (layer_h-20)//2) + 20}px; width:800px; font-size:11px; color:{tc}; line-height:1.3;">{desc}</p>'
            f'</div>'
        )
    return "\n".join(parts)


def _render_timeline(
    phases: list, primary: str, accent: str, bg: str, text_color: str, muted: str,
) -> str:
    """Render horizontal timeline with phase cards below a line."""
    n = min(len(phases), 6)
    if n == 0:
        return ""
    phase_w = min(200, (880 - (n - 1) * 20) // n)
    gap_x = (880 - n * phase_w) // max(1, n - 1) if n > 1 else 0
    line_top = 170
    card_top = 200
    card_h = 280
    parts = []
    # Horizontal line
    first_left = 40
    last_left = 40 + (n - 1) * (phase_w + gap_x)
    parts.append(
        f'<div style="position:absolute; left:{first_left}px; top:{line_top}px; '
        f'width:{last_left + phase_w - first_left}px; height:3px; background-color:{primary};"></div>'
    )
    for i, phase in enumerate(phases[:n]):
        label = _html.escape(str(phase.get("label", f"P{i+1}")))
        title = _html.escape(str(phase.get("title", "")))
        desc = _html.escape(str(phase.get("desc", "")))
        left = 40 + i * (phase_w + gap_x)
        dot_left = left + phase_w // 2
        parts.append(
            f'<div style="position:absolute; left:{dot_left - 8}px; top:{line_top - 6}px; '
            f'width:16px; height:16px; background-color:{accent}; border-radius:8px;"></div>'
        )
        parts.append(
            f'<p style="position:absolute; left:{left}px; top:{line_top - 34}px; width:{phase_w}px; '
            f'font-size:12px; color:{accent}; font-weight:bold; text-align:center;">{label}</p>'
        )
        parts.append(
            f'<div style="position:absolute; left:{left}px; top:{card_top}px; width:{phase_w}px; '
            f'height:{card_h}px; background-color:{bg}; border-top:3px solid {primary};">'
            f'<p style="position:absolute; left:10px; top:10px; width:{phase_w - 20}px; '
            f'font-size:13px; color:{primary}; font-weight:bold;">{title}</p>'
            f'<p style="position:absolute; left:10px; top:36px; width:{phase_w - 20}px; '
            f'font-size:11px; color:{muted}; line-height:1.5;">{desc}</p>'
            f'</div>'
        )
    return "\n".join(parts)


def _render_quadrant(
    cells: list, x_label: str, y_label: str,
    primary: str, accent: str, bg: str, text_color: str, muted: str,
) -> str:
    """Render 2x2 quadrant matrix. cells order: BL, BR, TL, TR."""
    if len(cells) < 4:
        cells = cells + [{"label": "", "items": []}] * (4 - len(cells))
    cell_w = 410
    cell_h = 200
    gap = 20
    left_start = 70
    top_start = 80
    parts = []
    x_esc = _html.escape(x_label)
    y_esc = _html.escape(y_label)
    parts.append(
        f'<p style="position:absolute; left:{left_start}px; top:{top_start + 2 * cell_h + gap + 12}px; '
        f'width:{2 * cell_w + gap}px; font-size:11px; color:{muted}; text-align:center;">{x_esc}</p>'
    )
    parts.append(
        f'<p style="position:absolute; left:20px; top:{top_start + cell_h}px; '
        f'font-size:11px; color:{muted}; transform:rotate(-90deg); transform-origin:center;">{y_esc}</p>'
    )
    positions = [
        (left_start, top_start + cell_h + gap),
        (left_start + cell_w + gap, top_start + cell_h + gap),
        (left_start, top_start),
        (left_start + cell_w + gap, top_start),
    ]
    shades = [_lighten(primary, 0.85), _lighten(accent, 0.85),
              _lighten(accent, 0.85), _lighten(primary, 0.85)]
    for i, ((cl, ct), cell) in enumerate(zip(positions, cells[:4])):
        label = _html.escape(str(cell.get("label", "")))
        items = cell.get("items", [])[:4]
        shade = shades[i]
        items_html = "".join(
            f'<p style="font-size:11px; color:{text_color}; line-height:1.5;">• {_html.escape(str(it))}</p>'
            for it in items
        )
        parts.append(
            f'<div style="position:absolute; left:{cl}px; top:{ct}px; width:{cell_w}px; height:{cell_h}px; '
            f'background-color:{shade}; border-radius:3px;">'
            f'<p style="position:absolute; left:10px; top:8px; font-size:13px; color:{primary}; font-weight:bold;">{label}</p>'
            f'<div style="position:absolute; left:10px; top:30px; width:{cell_w - 20}px; height:{cell_h - 40}px; overflow:hidden;">'
            f'{items_html}'
            f'</div>'
            f'</div>'
        )
    return "\n".join(parts)


def _render_role_columns(
    roles: list, primary: str, accent: str, bg: str, text_color: str, muted: str,
) -> str:
    """Render 3-4 role/object comparison columns."""
    n = min(len(roles), 4)
    if n == 0:
        return ""
    col_w = min(260, (880 - (n - 1) * 16) // n)
    gap_x = (880 - n * col_w) // max(1, n - 1) if n > 1 else 0
    top_start = 80
    col_h = 400
    parts = []
    for i, role in enumerate(roles[:n]):
        name = _html.escape(str(role.get("name", f"Role {i+1}")))
        subtitle = _html.escape(str(role.get("subtitle", "")))
        bullets = role.get("bullets", [])[:4]
        left = 40 + i * (col_w + gap_x)
        bullets_html = "".join(
            f'<p style="font-size:11px; color:{text_color}; line-height:1.5;">• {_html.escape(str(b))}</p>'
            for b in bullets
        )
        parts.append(
            f'<div style="position:absolute; left:{left}px; top:{top_start}px; width:{col_w}px; height:{col_h}px; '
            f'background-color:{bg}; border-top:4px solid {accent};">'
            f'<p style="position:absolute; left:12px; top:12px; font-size:15px; color:{primary}; font-weight:bold;">{name}</p>'
            f'<p style="position:absolute; left:12px; top:36px; font-size:11px; color:{muted};">{subtitle}</p>'
            f'<div style="position:absolute; left:12px; top:60px; width:{col_w - 24}px; height:{col_h - 72}px; overflow:hidden;">'
            f'{bullets_html}'
            f'</div>'
            f'</div>'
        )
    return "\n".join(parts)


def _lighten(hex_color: str, factor: float) -> str:
    """Lighten a hex color toward white. factor=1 → white, factor=0 → original."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


# ── IT diagram HTML builders ────────────────────────────────────────────

def _render_component_groups(
    groups: list, connections: list,
    primary: str, accent: str, bg: str, text_color: str, muted: str,
) -> str:
    """Render grouped component topology — vertical stacked groups with ↓ connectors."""
    if not groups:
        return ""
    n = len(groups)
    group_h = min(140, (420 - (n - 1) * 30) // n)
    total_h = n * group_h + (n - 1) * 30
    top_start = 10 + (430 - total_h) // 2
    parts = []
    for i, group in enumerate(groups[:6]):
        name = _html.escape(str(group.get("name", f"Group {i+1}")))
        components = group.get("components", [])
        top = top_start + i * (group_h + 30)
        # 组间箭头
        if i > 0:
            arrow_top = top - 28
            parts.append(
                f'<div style="position:absolute;left:440px;top:{arrow_top}px;width:80px;text-align:center;">'
                f'<p style="color:{muted};font-size:20px;margin:0;">↓</p></div>'
            )
            # 连线标签
            if i - 1 < len(connections):
                conn = connections[i - 1]
                label = _html.escape(str(conn.get("label", "")))
                if label:
                    parts.append(
                        f'<div style="position:absolute;left:530px;top:{arrow_top}px;">'
                        f'<p style="color:{accent};font-size:9px;margin:0;">{label}</p></div>'
                    )
        # 分组框
        parts.append(
            f'<div style="position:absolute;left:40px;top:{top}px;width:800px;height:{group_h}px;'
            f'border:2px solid {primary};border-radius:4px;background:rgba(255,255,255,0.6);">'
            f'<p style="position:absolute;left:12px;top:4px;font-size:11px;font-weight:bold;color:{primary};margin:0;">{name}</p>'
            f'</div>'
        )
        # 组件标签
        comp_strs = [_html.escape(str(c)) for c in components[:6]]
        if comp_strs:
            comp_html = ""
            comp_w = min(180, (780 - 10) // max(len(comp_strs), 1))
            for ci, comp in enumerate(comp_strs):
                comp_html += (
                    f'<div style="display:inline-block;margin:0 5px;padding:4px 10px;'
                    f'background:{accent};border-radius:3px;">'
                    f'<p style="color:#FFFFFF;font-size:10px;font-weight:bold;margin:0;">{comp}</p></div>'
                )
            parts.append(
                f'<div style="position:absolute;left:60px;top:{top + 30}px;width:760px;'
                f'display:flex;flex-wrap:wrap;align-items:center;gap:4px;">{comp_html}</div>'
            )
    return "\n".join(parts)


def _render_pipeline_stages(
    stages: list, flows: list,
    primary: str, accent: str, bg: str, text_color: str, muted: str,
) -> str:
    """Render horizontal data pipeline — source→transform→store→consume."""
    if not stages:
        return ""
    n = min(len(stages), 8)
    stage_w = min(150, (850 - (n - 1) * 40) // n)
    stage_h = 120
    total_w = n * stage_w + (n - 1) * 40
    start_x = (880 - total_w) // 2
    cy = 200

    _type_colors = {
        "source": primary,
        "transform": accent,
        "store": "#FFC000",
        "consume": "#70AD47",
    }

    parts = []
    for i, stage in enumerate(stages[:n]):
        label = _html.escape(str(stage.get("label", f"Stage {i+1}")))
        stype = str(stage.get("type", "")).lower()
        desc = _html.escape(str(stage.get("desc", "")))
        color = _type_colors.get(stype, primary)

        x = start_x + i * (stage_w + 40)

        # 箭头
        if i > 0:
            arrow_x = x - 35
            parts.append(
                f'<div style="position:absolute;left:{arrow_x}px;top:{cy + stage_h // 2 - 8}px;'
                f'width:30px;text-align:center;">'
                f'<p style="color:{muted};font-size:16px;margin:0;">→</p></div>'
            )
            # flow label
            if i - 1 < len(flows):
                flow_label = _html.escape(str(flows[i - 1].get("label", "")))
                if flow_label:
                    parts.append(
                        f'<div style="position:absolute;left:{arrow_x - 20}px;top:{cy + stage_h // 2 + 12}px;width:70px;">'
                        f'<p style="color:{accent};font-size:8px;margin:0;text-align:center;">{flow_label}</p></div>'
                    )

        # stage 形状
        border_style = f"border:2px solid {color}"
        bg_style = f"background:{color}"
        if stype == "source":
            border_style = f"border-left:6px solid {color};border:2px solid {color}"
        elif stype == "store":
            border_style = f"border-bottom:5px solid {color};border:2px solid {color}"

        parts.append(
            f'<div style="position:absolute;left:{x}px;top:{cy}px;width:{stage_w}px;height:{stage_h}px;'
            f'{bg_style};border-radius:4px;">'
            f'<p style="color:#FFFFFF;font-size:11px;font-weight:bold;text-align:center;margin:8px 4px 2px;">{label}</p>'
            f'<p style="color:rgba(255,255,255,0.8);font-size:8px;text-align:center;margin:0 4px;">{desc[:30]}</p>'
            f'</div>'
        )
        # type 标签
        if stype:
            parts.append(
                f'<div style="position:absolute;left:{x}px;top:{cy + stage_h + 6}px;width:{stage_w}px;">'
                f'<p style="color:{muted};font-size:8px;text-align:center;margin:0;">{stype.upper()}</p></div>'
            )
    return "\n".join(parts)


def _render_tech_matrix(
    categories: list,
    primary: str, accent: str, bg: str, text_color: str, muted: str,
) -> str:
    """Render tech stack comparison as HTML table."""
    if not categories:
        return ""
    # 收集所有唯一选项名
    all_options = []
    for cat in categories:
        for opt in cat.get("options", []):
            name = opt.get("name", "")
            if name and name not in all_options:
                all_options.append(name)
    if not all_options:
        return ""

    n_cols = len(all_options) + 1
    col_w = min(200, 860 // n_cols)
    cat_w = 860 - col_w * len(all_options)

    rows = []
    # 表头
    header = (
        f'<tr>'
        f'<td style="background:{primary};color:#FFFFFF;font-size:10px;font-weight:bold;padding:6px 8px;text-align:center;border:1px solid {primary};">类别</td>'
    )
    for opt in all_options:
        header += (
            f'<td style="background:{primary};color:#FFFFFF;font-size:10px;font-weight:bold;padding:6px 8px;text-align:center;border:1px solid {primary};">'
            f'{_html.escape(opt)}</td>'
        )
    header += '</tr>'
    rows.append(header)

    # 数据行
    for cat in categories[:6]:
        cat_name = _html.escape(str(cat.get("name", "")))
        cat_options = {opt.get("name", ""): opt.get("selected", False) for opt in cat.get("options", [])}
        row = (
            f'<tr>'
            f'<td style="background:rgba(0,61,110,0.08);color:{primary};font-size:10px;font-weight:bold;padding:6px 8px;border-left:4px solid {primary};border:1px solid #e0e0e0;">{cat_name}</td>'
        )
        for opt_name in all_options:
            selected = cat_options.get(opt_name, False)
            if selected:
                row += (
                    f'<td style="background:{primary};color:#FFFFFF;font-size:10px;font-weight:bold;padding:6px 8px;text-align:center;border:1px solid {primary};">'
                    f'■ {_html.escape(opt_name)}</td>'
                )
            else:
                row += (
                    f'<td style="background:#f8f8f8;color:{muted};font-size:10px;padding:6px 8px;text-align:center;border:1px solid #e0e0e0;">'
                    f'□</td>'
                )
        row += '</tr>'
        rows.append(row)

    table_html = (
        f'<table style="border-collapse:collapse;width:{cat_w + col_w * len(all_options)}px;font-family:\'Microsoft YaHei\',Arial,sans-serif;">'
        + "\n".join(rows)
        + '</table>'
    )
    return table_html
