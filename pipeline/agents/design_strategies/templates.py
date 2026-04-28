"""
TemplatePicker — heuristic template selection + slot building.

Extracted from HTMLDesignAgent so the agent class stays focused on orchestration.
All methods are static / class-level so the class is stateless.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_AUTO_ICONS = ["🎯", "💡", "📊", "⚙️", "🔍", "🚀", "🌟", "📈", "🛡️", "🤝"]
_COMPARISON_KEYWORDS = ("vs", " v.s.", "对比", "相比", "相较", "vs.", "对照", "差异", "区别")
_NUMERIC_TOKENS = ("%", "％", "亿", "万", "千", "倍", "x", "X", "k", "K", "M", "B")


class TemplatePicker:
    """Selects a template_id and builds the corresponding slot dict from slide data."""

    # layout_hint → template_id mapping
    LAYOUT_HINT_MAP: Dict[str, str] = {
        "parallel_points": "content_bullets",
        "comparison": "content_two_column",
        "metrics": "content_key_metrics",
        "chart_focus": "chart_focus",
        "quote_emphasis": "quote_highlight",
        "framework_grid": "icon_grid",
        "narrative": "timeline_horizontal",
    }

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #

    @staticmethod
    def pick(
        slide_data: Dict,
        body_blocks: List[Dict],
        bold_blocks: List[Dict],
        title: str,
    ) -> Tuple[str, Dict]:
        """Decision tree → (template_id, slots)."""

        picker = TemplatePicker

        # 0. hero pages → force hero_splash template
        if slide_data.get("page_weight") == "hero":
            return picker.build_slots(
                "hero_splash", slide_data, body_blocks, bold_blocks, title,
            )

        # 1. layout_hint short-circuit: if set, trust it directly
        hint = slide_data.get("layout_hint", "")
        if hint and hint in picker.LAYOUT_HINT_MAP:
            forced_template = picker.LAYOUT_HINT_MAP[hint]
            logger.info("layout_hint=%s → forcing template=%s", hint, forced_template)
            return picker.build_slots(
                forced_template, slide_data, body_blocks, bold_blocks, title,
            )

        # 1. Chart with real data → chart_focus
        if picker._chart_has_data(slide_data):
            annotations = []
            for b in body_blocks[:6]:
                c = b.get("content", "") if isinstance(b, dict) else str(b)
                if c:
                    annotations.append(c[:80])
            return "chart_focus", {
                "title": title,
                "annotations": annotations or ["关键趋势"],
            }

        # 1b. Diagram with structure → map diagram_type to template
        diagram = slide_data.get("diagram_spec")
        if isinstance(diagram, dict) and diagram.get("diagram_type"):
            dt = diagram["diagram_type"]
            _DIAGRAM_TEMPLATE_MAP = {
                "process_flow": "timeline_horizontal",
                "architecture": "architecture_stack",
                "framework": "quadrant_matrix",
                "relationship": "role_columns",
                # IT diagram types
                "tech_architecture": "tech_stack_layers",
                "component_topology": "component_network",
                "data_flow": "data_pipeline",
                "tech_stack_matrix": "tech_comparison",
            }
            tmpl = _DIAGRAM_TEMPLATE_MAP.get(dt, "framework_grid")
            logger.info("diagram_type=%s → template=%s", dt, tmpl)
            return picker.build_slots(tmpl, slide_data, body_blocks, bold_blocks, title)

        # 1c. Visual block with data → map type to template
        vblock = slide_data.get("visual_block")
        if isinstance(vblock, dict) and vblock.get("type"):
            vb_type = vblock["type"]
            items = vblock.get("items", [])
            if vb_type in ("kpi_cards", "stat_highlight") and items:
                metrics = []
                for item in items[:4]:
                    metrics.append({
                        "label": item.get("title", item.get("description", "")),
                        "value": item.get("value", ""),
                        "unit": "",
                        "note": item.get("description", item.get("trend", "")),
                    })
                logger.info("visual_block type=%s → content_key_metrics (%d items)", vb_type, len(metrics))
                return "content_key_metrics", {"title": title, "metrics": metrics}
            elif vb_type == "icon_text_grid" and items:
                logger.info("visual_block type=icon_text_grid → icon_grid (%d items)", len(items))
                return "icon_grid", {"title": title, "items": items}
            elif vb_type == "step_cards" and items:
                logger.info("visual_block type=step_cards → timeline_horizontal (%d items)", len(items))
                phases = []
                for idx, item in enumerate(items[:6]):
                    phases.append({
                        "label": item.get("label", f"步骤{idx+1}"),
                        "title": item.get("title", item.get("name", ""))[:30],
                        "desc": item.get("description", item.get("desc", ""))[:60],
                    })
                return "timeline_horizontal", {"title": title, "phases": phases}
            elif vb_type == "comparison_columns" and items:
                logger.info("visual_block type=comparison_columns → content_two_column")
                return picker.build_slots("content_two_column", slide_data, body_blocks, bold_blocks, title)

        n_blocks = len(body_blocks)

        # 2. Comparison intent → content_two_column
        if picker._looks_like_comparison(title, body_blocks) and n_blocks >= 2:
            left, right = picker._split_comparison(body_blocks)
            return "content_two_column", {
                "title": title,
                "left_label": picker._infer_column_label(left, "方案A"),
                "left_bullets": left,
                "right_label": picker._infer_column_label(right, "方案B"),
                "right_bullets": right,
            }

        # 3. Numeric-heavy blocks → content_key_metrics
        numeric_blocks = [b for b in body_blocks if picker._has_numeric(
            b.get("content", "") if isinstance(b, dict) else str(b)
        )]
        if len(numeric_blocks) >= 2:
            metrics = []
            for b in numeric_blocks[:4]:
                m = picker._extract_metric(b)
                if m:
                    metrics.append(m)
            if len(metrics) >= 2:
                sub_bullets = []
                for b in body_blocks:
                    if b not in numeric_blocks:
                        c = b.get("content", "") if isinstance(b, dict) else str(b)
                        if c:
                            sub_bullets.append(c[:60])
                return "content_key_metrics", {
                    "title": title,
                    "metrics": metrics,
                    "sub_bullets": sub_bullets[:3],
                }

        # 4. 3-6 short parallel blocks → icon_grid
        if 3 <= n_blocks <= 6:
            max_len = max(len(b.get("content", "") if isinstance(b, dict) else str(b)) for b in body_blocks)
            if max_len <= 60:
                items = []
                for idx, b in enumerate(body_blocks):
                    content = b.get("content", "") if isinstance(b, dict) else str(b)
                    icon = _AUTO_ICONS[idx % len(_AUTO_ICONS)]
                    if len(content) <= 15:
                        items.append({"icon": icon, "title": content, "desc": ""})
                    else:
                        mid = min(len(content), 20)
                        # Try to split at a punctuation
                        for sep in ["：", ":", "—", "-", "，", ","]:
                            pos = content.find(sep)
                            if 0 < pos < 40:
                                mid = pos
                                break
                        items.append({
                            "icon": icon,
                            "title": content[:mid].rstrip("：:—-，, "),
                            "desc": content[mid:].lstrip("：:—-，, ")[:60],
                        })
                return "icon_grid", {"title": title, "items": items}

        # 5. Everything else → content_bullets
        bullets = []
        for b in body_blocks[:8]:
            c = b.get("content", "") if isinstance(b, dict) else str(b)
            if c:
                bullets.append(c[:80])
        return "content_bullets", {
            "title": title,
            "bullets": bullets,
            "has_chart": bool(slide_data.get("chart_suggestion")),
        }

    # ------------------------------------------------------------------ #
    # Slot builder — builds slots for a given template_id
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_slots(
        template_id: str,
        slide_data: Dict,
        body_blocks: List[Dict],
        bold_blocks: List[Dict],
        title: str,
    ) -> Tuple[str, Dict]:
        """Build minimal slots for a forced template_id (layout_hint path)."""
        picker = TemplatePicker

        if template_id == "chart_focus":
            annotations = []
            for b in body_blocks[:6]:
                c = b.get("content", "") if isinstance(b, dict) else str(b)
                if c:
                    annotations.append(c[:80])
            return template_id, {"title": title, "annotations": annotations or ["关键趋势"]}

        if template_id == "content_two_column":
            left, right = picker._split_comparison(body_blocks)
            return template_id, {
                "title": title,
                "left_label": picker._infer_column_label(left, "方案A"),
                "left_bullets": left,
                "right_label": picker._infer_column_label(right, "方案B"),
                "right_bullets": right,
            }

        if template_id == "content_key_metrics":
            metrics = []
            for b in body_blocks[:4]:
                m = picker._extract_metric(b)
                if m:
                    metrics.append(m)
            if not metrics:
                metrics = [{"label": "指标", "value": "-", "unit": "", "note": ""}]
            return template_id, {"title": title, "metrics": metrics}

        if template_id == "quote_highlight":
            quote = body_blocks[0].get("content", "")[:120] if body_blocks else title[:120]
            sub_bullets = []
            for b in body_blocks[1:6]:
                c = b.get("content", "") if isinstance(b, dict) else str(b)
                if c:
                    sub_bullets.append(c[:60])
            return template_id, {"title": title, "quote_text": quote, "sub_bullets": sub_bullets}

        if template_id == "icon_grid":
            items = []
            for idx, b in enumerate(body_blocks[:6]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                icon = _AUTO_ICONS[idx % len(_AUTO_ICONS)]
                if len(content) <= 20:
                    items.append({"icon": icon, "title": content, "desc": ""})
                else:
                    mid = min(len(content), 30)
                    for sep in ["：", ":", "—", "-"]:
                        pos = content.find(sep)
                        if 0 < pos < 50:
                            mid = pos
                            break
                    items.append({
                        "icon": icon,
                        "title": content[:mid].rstrip("：:—-，, "),
                        "desc": content[mid:].lstrip("：:—-，, ")[:60],
                    })
            return template_id, {"title": title, "items": items or [{"icon": "📊", "title": title, "desc": ""}]}

        if template_id == "timeline_horizontal":
            phases = []
            for idx, b in enumerate(body_blocks[:6]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                phases.append({"label": f"阶段{idx+1}", "title": content[:30], "desc": content[:60]})
            return template_id, {"title": title, "phases": phases or [{"label": "阶段1", "title": title, "desc": ""}]}

        if template_id == "architecture_stack":
            layers = []
            for idx, b in enumerate(body_blocks[:6]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                layers.append({"name": content[:20], "desc": content[:60]})
            return template_id, {"title": title, "layers": layers or [{"name": "Layer 1", "desc": ""}]}

        if template_id == "quadrant_matrix":
            cells = []
            for idx, b in enumerate(body_blocks[:4]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                cells.append({"label": f"象限{idx+1}", "items": [content[:50]]})
            while len(cells) < 4:
                cells.append({"label": "", "items": []})
            return template_id, {"title": title, "x_label": "维度A", "y_label": "维度B", "cells": cells}

        if template_id == "role_columns":
            roles = []
            for idx, b in enumerate(body_blocks[:4]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                roles.append({"name": content[:20], "subtitle": "", "bullets": [content[:50]]})
            return template_id, {"title": title, "roles": roles or [{"name": "角色1", "subtitle": "", "bullets": []}]}

        if template_id == "hero_splash":
            # Extract the most impactful number from text blocks
            all_text = " ".join(
                b.get("content", "") if isinstance(b, dict) else str(b)
                for b in body_blocks
            )
            # Find numbers with units (亿, 万, %, etc.)
            num_match = re.search(r'(\d+\.?\d*)\s*(亿|万|%|亿元|万元|个|家|人|美元)', all_text)
            big_number = ""
            number_caption = ""
            if num_match:
                big_number = num_match.group(1) + num_match.group(2)
                # Try to find context before the number
                prefix = all_text[:num_match.start()].rstrip("，。、：: ")
                # Find last meaningful phrase
                for sep in ["，", "。", "、", "：", "："]:
                    idx = prefix.rfind(sep)
                    if idx >= 0:
                        prefix = prefix[idx+1:]
                        break
                number_caption = prefix[:30] if prefix else ""
            if not big_number:
                big_number = title[:10] if title else "—"
            # Subtitle: second text block or takeaway
            subtitle = ""
            if len(body_blocks) > 1:
                subtitle = (body_blocks[1].get("content", "") if isinstance(body_blocks[1], dict) else str(body_blocks[1]))[:40]
            if not subtitle:
                subtitle = slide_data.get("takeaway_message", "")[:40]
            return template_id, {
                "headline": slide_data.get("takeaway_message", title),
                "big_number": big_number,
                "number_caption": number_caption,
                "subtitle": subtitle,
            }

        # ── IT diagram slot builders (prefer diagram_spec data, fallback body_blocks) ──

        if template_id == "tech_stack_layers":
            diagram = slide_data.get("diagram_spec", {})
            layers_raw = diagram.get("layers", [])
            if layers_raw:
                layers = []
                for l in layers_raw[:7]:
                    items = l.get("items", [])
                    desc = ", ".join(str(i) for i in items) if isinstance(items, list) else str(items)
                    layer = {"name": str(l.get("label", ""))[:20], "desc": desc[:60]}
                    if l.get("color"):
                        layer["color"] = l["color"]
                    layers.append(layer)
            else:
                layers = [{"name": b.get("content", "")[:20] if isinstance(b, dict) else str(b)[:20], "desc": ""}
                          for b in body_blocks[:7]]
            return template_id, {"title": title, "layers": layers or [{"name": "Layer 1", "desc": ""}]}

        if template_id == "component_network":
            diagram = slide_data.get("diagram_spec", {})
            groups_raw = diagram.get("groups", [])
            if groups_raw:
                groups = []
                for g in groups_raw[:6]:
                    comps = g.get("components", [])
                    groups.append({"name": str(g.get("name", ""))[:20],
                                   "components": [str(c) for c in comps[:6]]})
            else:
                groups = [{"name": b.get("content", "")[:20] if isinstance(b, dict) else str(b)[:20],
                           "components": []} for b in body_blocks[:6]]
            connections = diagram.get("connections", []) if isinstance(diagram, dict) else []
            return template_id, {"title": title, "groups": groups, "connections": connections}

        if template_id == "data_pipeline":
            diagram = slide_data.get("diagram_spec", {})
            stages_raw = diagram.get("stages", [])
            if stages_raw:
                stages = []
                for s in stages_raw[:8]:
                    stages.append({"label": str(s.get("label", ""))[:20],
                                   "type": str(s.get("type", "")),
                                   "desc": str(s.get("desc", ""))[:30]})
            else:
                stages = [{"label": b.get("content", "")[:20] if isinstance(b, dict) else str(b)[:20],
                           "type": "", "desc": ""} for b in body_blocks[:8]]
            flows = diagram.get("flows", []) if isinstance(diagram, dict) else []
            return template_id, {"title": title, "stages": stages, "flows": flows}

        if template_id == "tech_comparison":
            diagram = slide_data.get("diagram_spec", {})
            cats_raw = diagram.get("categories", [])
            if cats_raw:
                categories = []
                for c in cats_raw[:6]:
                    opts = c.get("options", [])
                    categories.append({"name": str(c.get("name", ""))[:15],
                                       "options": opts})
            else:
                categories = [{"name": b.get("content", "")[:15] if isinstance(b, dict) else str(b)[:15],
                               "options": []} for b in body_blocks[:6]]
            return template_id, {"title": title, "categories": categories}

        # Default: content_bullets
        bullets = []
        for b in body_blocks[:8]:
            c = b.get("content", "") if isinstance(b, dict) else str(b)
            if c:
                bullets.append(c[:80])
        return template_id, {
            "title": title,
            "bullets": bullets,
            "has_chart": bool(slide_data.get("chart_suggestion")),
        }

    # ------------------------------------------------------------------ #
    # Helper methods (private, used only by pick / build_slots)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _chart_has_data(slide_data: Dict) -> bool:
        """Check whether chart_suggestion contains real data rows."""
        chart = slide_data.get("chart_suggestion") or {}
        if isinstance(chart, dict):
            series = chart.get("series") or chart.get("data")
            if isinstance(series, list) and len(series) > 0:
                return True
            labels = chart.get("labels") or chart.get("categories")
            if isinstance(labels, list) and len(labels) > 0:
                return True
        return False

    @staticmethod
    def _looks_like_comparison(title: str, blocks: List[Dict]) -> bool:
        """Detect comparison intent from title or block content."""
        text = title.lower()
        for block in blocks[:4]:
            text += " " + (block.get("content", "") if isinstance(block, dict) else str(block)).lower()
        for kw in _COMPARISON_KEYWORDS:
            if kw.lower() in text:
                return True
        return False

    @staticmethod
    def _split_comparison(blocks: List[Dict]) -> Tuple[List[str], List[str]]:
        """Split text blocks into two groups at a comparison keyword boundary."""
        left, right = [], []
        flipped = False
        for block in blocks:
            content = block.get("content", "") if isinstance(block, dict) else str(block)
            if not flipped:
                for kw in _COMPARISON_KEYWORDS:
                    if kw in content:
                        flipped = True
                        break
                if not flipped:
                    left.append(content)
            else:
                right.append(content)
        # If no keyword found, split in half
        if not right and len(blocks) >= 4:
            mid = len(blocks) // 2
            left = [b.get("content", "") if isinstance(b, dict) else str(b) for b in blocks[:mid]]
            right = [b.get("content", "") if isinstance(b, dict) else str(b) for b in blocks[mid:]]
        return left[:4], right[:4]

    @staticmethod
    def _infer_column_label(items: List[str], fallback: str) -> str:
        """Try to extract a short label from the first item, else use fallback."""
        if not items:
            return fallback
        first = items[0]
        # Take first 12 chars as label
        if len(first) <= 12:
            return first.rstrip("：: ")
        return first[:12].rstrip("：: ") + "…"

    @staticmethod
    def _has_numeric(text: str) -> bool:
        """Check if text contains numeric indicators."""
        for tok in _NUMERIC_TOKENS:
            if tok in text:
                return True
        # Also check for plain digits
        return bool(re.search(r"\d+\.?\d*", text))

    @staticmethod
    def _extract_metric(block: Dict) -> Optional[Dict[str, str]]:
        """Try to extract {label, value, unit, note} from a text block."""
        content = block.get("content", "") if isinstance(block, dict) else str(block)
        if not content:
            return None
        # Find the first numeric token
        m = re.search(r"([\d,]+\.?\d*)\s*(%|％|亿|万|倍|元|美元|k|K|M|B)?", content)
        if not m:
            return None
        value = m.group(1)
        unit = m.group(2) or ""
        # Label: text before the number (up to 15 chars)
        prefix = content[:m.start()].strip().rstrip("：:，,、是为达约超近")
        label = prefix[-15:] if len(prefix) > 15 else prefix
        if not label:
            label = "指标"
        # Note: text after the number
        rest = content[m.end():].strip().lstrip("，,。.、 ")
        note = rest[:60] if rest else ""
        return {"label": label, "value": value, "unit": unit, "note": note}
