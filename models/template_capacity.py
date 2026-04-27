"""
Template Capacity Model — single source of truth for slide display constraints.

Every pipeline stage that generates or processes content should reference
LAYOUT_CAPACITIES to know how much fits on a slide.
"""

LAYOUT_CAPACITIES: dict[str, dict] = {
    "parallel_points": {
        "template": "content_bullets",
        "max_items": 8,
        "max_chars_per_item": 80,
        "description": "并列论据布局",
        "content_instruction": (
            "text_blocks 应包含 4-8 条独立并列的论据，每条一句话，每条不超过80字"
        ),
    },
    "comparison": {
        "template": "content_two_column",
        "max_items_per_side": 6,
        "max_chars_per_item": 60,
        "description": "两方对比布局",
        "content_instruction": (
            "text_blocks 分为两组（方案A / 方案B），每组各含 2-6 条要点，每条不超过60字"
        ),
    },
    "metrics": {
        "template": "content_key_metrics",
        "max_metrics": 4,
        "max_sub_bullets": 4,
        "description": "数据指标布局",
        "content_instruction": (
            "text_blocks 应包含 3-4 个含具体数字的要点（百分比、金额、倍数等），每条一句话"
        ),
    },
    "chart_focus": {
        "template": "chart_focus",
        "max_annotations": 6,
        "max_chars_per_annotation": 80,
        "description": "图表注解布局",
        "content_instruction": (
            "text_blocks 应提供 3-6 条图表解读/标注，每条不超过80字，补充 chart_suggestion"
        ),
    },
    "quote_emphasis": {
        "template": "quote_highlight",
        "max_quote_chars": 120,
        "max_sub_bullets": 5,
        "max_chars_per_sub": 60,
        "description": "核心结论强调",
        "content_instruction": (
            "第1条 text_block 为核心结论（不超过120字），后续 3-5 条为支撑论据（每条不超过60字）"
        ),
    },
    "framework_grid": {
        "template": "quadrant_matrix",
        "max_cells": 4,
        "max_items_per_cell": 4,
        "description": "2×2象限/分层",
        "content_instruction": (
            "text_blocks 按象限或层级组织，每部分 1-3 条描述"
        ),
    },
    "narrative": {
        "template": "timeline_horizontal",
        "max_phases": 6,
        "max_chars_per_phase": 60,
        "description": "时间线/流程",
        "content_instruction": (
            "text_blocks 按阶段/步骤顺序排列，3-6 个阶段，每阶段 1-2 条要点"
        ),
    },
}

DEFAULT_LAYOUT = "parallel_points"
