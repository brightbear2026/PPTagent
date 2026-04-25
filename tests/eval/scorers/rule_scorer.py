"""
rule_scorer.py — 规则评分（结构合规性）
防结构退化：不依赖 LLM，纯规则判断。
"""

from __future__ import annotations
import re
from typing import Any


def score_outline(outline: dict) -> dict:
    """
    对 outline 阶段输出打规则分。

    Returns:
        dict with keys: action_title_ratio, scqa_completeness, section_balance,
                        structural_injection, overall (0-1)
    """
    items = outline.get("items", outline.get("slides", []))
    scqa = outline.get("scqa", {})

    # ── 1. action_title_ratio ──────────────────────────────────
    # takeaway_message 含动词（包含至少2个汉字且包含常见动词特征）的比率
    verb_pattern = re.compile(
        r'[增减提降实现推进完成达到超过落实保持维持加速推动建立建设实施部署优化改善扩大缩小]'
        r'|[是为了将要通过]',
        re.UNICODE,
    )
    content_slides = [
        s for s in items
        if s.get("slide_type") not in ("title", "agenda", "section_divider")
    ]
    if content_slides:
        has_verb = sum(
            1 for s in content_slides
            if verb_pattern.search(s.get("takeaway_message", ""))
        )
        action_title_ratio = has_verb / len(content_slides)
    else:
        action_title_ratio = 0.0

    # ── 2. scqa_completeness ──────────────────────────────────
    # scqa 所有字段非空
    if scqa:
        non_empty = sum(1 for v in scqa.values() if v and str(v).strip())
        scqa_completeness = non_empty / max(len(scqa), 1)
    else:
        scqa_completeness = 0.0

    # ── 3. section_balance ──────────────────────────────────
    # 各章节 slide 数标准差（越小越好；转换为 0-1 分，std<3 得满分）
    from collections import Counter
    sections = [
        s.get("section", "")
        for s in items
        if s.get("slide_type") not in ("title", "agenda", "section_divider")
        and s.get("section", "").strip()
    ]
    if sections:
        counts = list(Counter(sections).values())
        mean = sum(counts) / len(counts)
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        std = variance ** 0.5
        # std=0 → 1.0, std=3 → 0.0, std>3 → 0.0
        section_balance = max(0.0, 1.0 - std / 3.0)
    else:
        section_balance = 0.5  # no sections → neutral

    # ── 4. structural_injection ──────────────────────────────────
    # agenda 和 section_divider 是否被正确注入
    has_agenda = any(s.get("slide_type") == "agenda" for s in items)
    section_dividers = [s for s in items if s.get("slide_type") == "section_divider"]
    unique_sections = {
        s.get("section", "") for s in items
        if s.get("slide_type") not in ("title", "agenda", "section_divider")
        and s.get("section", "").strip()
    }
    if len(unique_sections) >= 2:
        structural_injection = 1.0 if (has_agenda and len(section_dividers) >= 2) else 0.0
    else:
        structural_injection = 1.0  # single section → no injection needed

    # ── Overall ──────────────────────────────────
    overall = (action_title_ratio * 0.4 + scqa_completeness * 0.2
               + section_balance * 0.2 + structural_injection * 0.2)

    return {
        "action_title_ratio": round(action_title_ratio, 3),
        "scqa_completeness": round(scqa_completeness, 3),
        "section_balance": round(section_balance, 3),
        "structural_injection": round(structural_injection, 3),
        "outline_overall": round(overall, 3),
    }


def score_content(content: dict) -> dict:
    """
    对 content 阶段输出打规则分。

    Returns:
        dict with keys: text_blocks_nonempty_ratio, chart_validity, overall (0-1)
    """
    slides = content.get("slides", [])
    if not slides:
        return {"text_blocks_nonempty_ratio": 0.0, "chart_validity": 0.0, "content_overall": 0.0}

    # ── 1. text_blocks_nonempty_ratio ──────────────────────────────────
    # text_blocks 非空的页面占比
    nonempty = sum(
        1 for s in slides
        if any(b.get("content", "").strip() for b in s.get("text_blocks", []))
    )
    text_blocks_nonempty_ratio = nonempty / len(slides)

    # ── 2. chart_validity ──────────────────────────────────
    # primary_visual='chart' 的页面中，chart_suggestion 有效（有 chart_type + series）的比率
    chart_slides = [s for s in slides if s.get("primary_visual") == "chart"]
    if chart_slides:
        valid_charts = sum(
            1 for s in chart_slides
            if s.get("chart_suggestion")
            and s["chart_suggestion"].get("chart_type")
            and s["chart_suggestion"].get("series")
        )
        chart_validity = valid_charts / len(chart_slides)
    else:
        chart_validity = 1.0  # no chart slides → not penalized

    # ── Overall ──────────────────────────────────
    overall = text_blocks_nonempty_ratio * 0.7 + chart_validity * 0.3

    return {
        "text_blocks_nonempty_ratio": round(text_blocks_nonempty_ratio, 3),
        "chart_validity": round(chart_validity, 3),
        "content_overall": round(overall, 3),
    }
