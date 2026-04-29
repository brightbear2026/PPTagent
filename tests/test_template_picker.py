"""
Tests for TemplatePicker — visual_block-first slot building + mutual exclusion.

Covers:
- visual_block structured data maps to correct slots
- No visual_block → fallback to content_bullets (not heuristic splitting)
- Mutual exclusion: primary_visual clears conflicting visual fields
- Hero demote: page_weight=hero + blocks>=4 → content_key_metrics
- Hero splash: page_weight=hero + blocks<=3 → hero_splash
"""

import pytest
from unittest.mock import patch

from pipeline.agents.design_strategies.templates import TemplatePicker


# ── Helpers ──

def _body_blocks(texts):
    """Create body_blocks list from plain text strings."""
    return [{"content": t} for t in texts]


def _slide_data(**overrides):
    """Base slide_data with sensible defaults."""
    base = {
        "page_number": 1,
        "takeaway_message": "核心观点",
        "primary_visual": "text",
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════
# 1. visual_block → correct slot mapping
# ═══════════════════════════════════════════════════════════════

class TestVisualBlockMapping:

    def test_hero_splash_stat_highlight(self):
        sd = _slide_data(
            visual_block={"type": "stat_highlight", "items": [
                {"title": "市场规模", "value": "1254亿元", "description": "2024年六大行投入合计"},
            ]},
        )
        tid, slots = TemplatePicker.build_slots(
            "hero_splash", sd, _body_blocks(["some text"]), [], "标题",
        )
        assert tid == "hero_splash"
        assert slots["big_number"] == "1254亿元"
        assert slots["number_caption"] == "市场规模"
        assert slots["subtitle"] == "2024年六大行投入合计"
        assert slots["headline"] == "核心观点"

    def test_content_key_metrics_kpi_cards(self):
        sd = _slide_data(
            visual_block={"type": "kpi_cards", "items": [
                {"title": "营收", "value": "32%", "description": "同比增长"},
                {"title": "利润", "value": "5.6亿", "description": "净利润"},
            ]},
        )
        tid, slots = TemplatePicker.build_slots(
            "content_key_metrics", sd, _body_blocks(["营收32%"]), [], "标题",
        )
        assert tid == "content_key_metrics"
        assert len(slots["metrics"]) == 2
        assert slots["metrics"][0]["label"] == "营收"
        assert slots["metrics"][0]["value"] == "32%"
        assert slots["metrics"][1]["label"] == "利润"

    def test_icon_grid_icon_text_grid(self):
        sd = _slide_data(
            visual_block={"type": "icon_text_grid", "items": [
                {"title": "原则一", "description": "客户至上"},
                {"title": "原则二", "description": "数据驱动"},
            ]},
        )
        tid, slots = TemplatePicker.build_slots(
            "icon_grid", sd, _body_blocks(["原则一：客户至上", "原则二：数据驱动"]), [], "标题",
        )
        assert tid == "icon_grid"
        assert len(slots["items"]) == 2
        assert slots["items"][0]["title"] == "原则一"
        assert slots["items"][0]["desc"] == "客户至上"

    def test_timeline_step_cards(self):
        sd = _slide_data(
            visual_block={"type": "step_cards", "items": [
                {"label": "阶段1", "title": "起步", "description": "建立基线"},
                {"label": "阶段2", "title": "增长", "description": "快速扩张"},
            ]},
        )
        tid, slots = TemplatePicker.build_slots(
            "timeline_horizontal", sd, _body_blocks(["起步", "增长"]), [], "标题",
        )
        assert tid == "timeline_horizontal"
        assert len(slots["phases"]) == 2
        assert slots["phases"][0]["label"] == "阶段1"
        assert slots["phases"][0]["title"] == "起步"
        assert slots["phases"][1]["desc"] == "快速扩张"

    def test_content_two_column_comparison_columns(self):
        sd = _slide_data(
            visual_block={"type": "comparison_columns", "items": [
                {"title": "方案A优势"},
                {"title": "方案A成本"},
                {"title": "方案B优势"},
                {"title": "方案B成本"},
            ]},
        )
        tid, slots = TemplatePicker.build_slots(
            "content_two_column", sd, _body_blocks(["a", "b", "c", "d"]), [], "标题",
        )
        assert tid == "content_two_column"
        assert len(slots["left_bullets"]) == 2
        assert len(slots["right_bullets"]) == 2


# ═══════════════════════════════════════════════════════════════
# 2. No visual_block → fallback to content_bullets
# ═══════════════════════════════════════════════════════════════

class TestFallbackToBullets:

    def test_icon_grid_no_vblock(self):
        sd = _slide_data()
        tid, slots = TemplatePicker.build_slots(
            "icon_grid", sd, _body_blocks(["a", "b", "c"]), [], "标题",
        )
        assert tid == "content_bullets"

    def test_timeline_no_vblock(self):
        sd = _slide_data()
        tid, slots = TemplatePicker.build_slots(
            "timeline_horizontal", sd, _body_blocks(["阶段1内容", "阶段2内容"]), [], "标题",
        )
        assert tid == "content_bullets"

    def test_architecture_stack_no_vblock(self):
        sd = _slide_data()
        tid, slots = TemplatePicker.build_slots(
            "architecture_stack", sd, _body_blocks(["层1", "层2"]), [], "标题",
        )
        assert tid == "content_bullets"

    def test_quadrant_matrix_no_vblock(self):
        sd = _slide_data()
        tid, slots = TemplatePicker.build_slots(
            "quadrant_matrix", sd, _body_blocks(["q1", "q2", "q3", "q4"]), [], "标题",
        )
        assert tid == "content_bullets"

    def test_role_columns_no_vblock(self):
        sd = _slide_data()
        tid, slots = TemplatePicker.build_slots(
            "role_columns", sd, _body_blocks(["角色1", "角色2"]), [], "标题",
        )
        assert tid == "content_bullets"

    def test_content_key_metrics_no_vblock_extracts_metrics(self):
        """content_key_metrics fallback extracts from numeric blocks (no sub_bullets)."""
        sd = _slide_data()
        tid, slots = TemplatePicker.build_slots(
            "content_key_metrics", sd, _body_blocks([
                "营收增长32%，连续三季度领跑",
                "市场份额从18%提升至24%",
            ]), [], "标题",
        )
        assert tid == "content_key_metrics"
        assert len(slots["metrics"]) >= 1

    def test_content_key_metrics_no_numeric_fallback(self):
        """No numeric blocks → still returns metrics with placeholder."""
        sd = _slide_data()
        tid, slots = TemplatePicker.build_slots(
            "content_key_metrics", sd, _body_blocks(["纯文本没有数字"]), [], "标题",
        )
        assert tid == "content_key_metrics"
        assert slots["metrics"][0]["value"] == "-"

    def test_hero_splash_no_vblock_falls_to_regex(self):
        """hero_splash without visual_block still uses regex extraction."""
        sd = _slide_data()
        tid, slots = TemplatePicker.build_slots(
            "hero_splash", sd, _body_blocks(["市场规模达1254亿元"]), [], "标题",
        )
        assert tid == "hero_splash"
        assert "1254" in slots["big_number"]


# ═══════════════════════════════════════════════════════════════
# 3. pick() decision tree
# ═══════════════════════════════════════════════════════════════

class TestPickDecisionTree:

    def test_hero_demote_4_blocks(self):
        """hero + 4+ blocks → demoted to content_key_metrics."""
        sd = _slide_data(page_weight="hero")
        tid, slots = TemplatePicker.pick(
            sd, _body_blocks(["a", "b", "c", "d"]), [], "标题",
        )
        assert tid == "content_key_metrics"

    def test_hero_splash_3_blocks(self):
        """hero + ≤3 blocks → hero_splash."""
        sd = _slide_data(page_weight="hero")
        tid, slots = TemplatePicker.pick(
            sd, _body_blocks(["市场规模1254亿元"]), [], "标题",
        )
        assert tid == "hero_splash"

    def test_layout_hint_short_circuit(self):
        """layout_hint overrides heuristics."""
        sd = _slide_data(layout_hint="narrative")
        tid, slots = TemplatePicker.pick(
            sd, _body_blocks(["a", "b"]), [], "标题",
        )
        # Without visual_block, build_slots("timeline_horizontal") falls to content_bullets
        assert tid == "content_bullets"

    def test_layout_hint_with_vblock(self):
        """layout_hint + visual_block → correct template."""
        sd = _slide_data(
            layout_hint="narrative",
            visual_block={"type": "step_cards", "items": [
                {"label": "阶段1", "title": "起步", "description": "建立基线"},
            ]},
        )
        tid, slots = TemplatePicker.pick(
            sd, _body_blocks(["a", "b"]), [], "标题",
        )
        assert tid == "timeline_horizontal"
        assert slots["phases"][0]["title"] == "起步"

    def test_chart_data_overrides(self):
        """primary_visual=chart → chart_focus."""
        sd = _slide_data(
            primary_visual="chart",
            chart_suggestion={"chart_type": "bar", "categories": ["A", "B"], "series": [{"values": [1, 2]}]},
        )
        tid, slots = TemplatePicker.pick(
            sd, _body_blocks(["a", "b"]), [], "标题",
        )
        assert tid == "chart_focus"

    def test_vblock_kpi_cards_picked(self):
        """primary_visual=visual_block + kpi_cards → content_key_metrics."""
        sd = _slide_data(
            primary_visual="visual_block",
            visual_block={"type": "kpi_cards", "items": [
                {"title": "营收", "value": "32%", "description": "增长"},
            ]},
        )
        tid, slots = TemplatePicker.pick(
            sd, _body_blocks(["a"]), [], "标题",
        )
        assert tid == "content_key_metrics"
        assert slots["metrics"][0]["label"] == "营收"

    def test_default_content_bullets(self):
        """No special markers → content_bullets."""
        sd = _slide_data()
        tid, slots = TemplatePicker.pick(
            sd, _body_blocks(["论点一", "论点二", "论点三"]), [], "标题",
        )
        assert tid == "content_bullets"

    def test_icon_grid_heuristic_skipped_without_vblock(self):
        """pick() icon_grid heuristic: no vblock → skip, not split."""
        sd = _slide_data()
        blocks = _body_blocks(["短句一", "短句二", "短句三"])
        tid, slots = TemplatePicker.pick(sd, blocks, [], "标题")
        # 3 short blocks without visual_block → content_bullets, not icon_grid
        assert tid == "content_bullets"

    def test_icon_grid_heuristic_with_vblock(self):
        """primary_visual=visual_block + icon_text_grid → icon_grid."""
        sd = _slide_data(
            primary_visual="visual_block",
            visual_block={"type": "icon_text_grid", "items": [
                {"title": "要点一", "description": "说明"},
                {"title": "要点二", "description": "说明"},
                {"title": "要点三", "description": "说明"},
            ]},
        )
        blocks = _body_blocks(["短句一", "短句二", "短句三"])
        tid, slots = TemplatePicker.pick(sd, blocks, [], "标题")
        assert tid == "icon_grid"
        assert len(slots["items"]) == 3


# ═══════════════════════════════════════════════════════════════
# 4. Schema guarantee (ContentSlideSchema enforces mutual exclusion;
#    _match_slides only logs warnings, no longer clears fields)
# ═══════════════════════════════════════════════════════════════

class TestSchemaGuarantee:

    def test_pv_chart_with_valid_data_passes(self):
        """primary_visual=chart with valid chart_suggestion should produce correct template."""
        sd = _slide_data(
            primary_visual="chart",
            chart_suggestion={"chart_type": "bar", "series": [{"values": [1, 2]}]},
        )
        tid, slots = TemplatePicker.pick(sd, _body_blocks(["a"]), [], "标题")
        assert tid == "chart_focus"

    def test_pv_visual_block_picks_correct_template(self):
        """primary_visual=visual_block routes through _pick_vblock_template."""
        sd = _slide_data(
            primary_visual="visual_block",
            visual_block={"type": "kpi_cards", "items": [
                {"title": "营收", "value": "32%"},
            ]},
        )
        tid, slots = TemplatePicker.pick(sd, _body_blocks(["a"]), [], "标题")
        assert tid == "content_key_metrics"

    def test_pv_text_only_uses_text_heuristics(self):
        """primary_visual=text_only falls through to text-content heuristics."""
        sd = _slide_data(primary_visual="text_only")
        tid, slots = TemplatePicker.pick(sd, _body_blocks(["要点一", "要点二"]), [], "标题")
        assert tid == "content_bullets"

    def test_no_pv_defaults_to_text_only(self):
        """Empty primary_visual → text_only, text heuristics apply."""
        sd = _slide_data(primary_visual="")
        tid, slots = TemplatePicker.pick(sd, _body_blocks(["a"]), [], "标题")
        assert tid == "content_bullets"
