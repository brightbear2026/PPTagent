"""Tests for LayoutTemplate Registry and call_to_action layout (Phase 3 pilot)."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pydantic


class TestLayoutRegistry:
    def test_registry_has_call_to_action(self):
        from pipeline.layouts import LayoutRegistry
        assert "call_to_action" in LayoutRegistry.names()

    def test_registry_get_returns_layout(self):
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("call_to_action")
        assert layout.name == "call_to_action"

    def test_registry_unknown_name_raises(self):
        from pipeline.layouts import LayoutRegistry
        with pytest.raises(KeyError):
            LayoutRegistry.get("nonexistent_layout")

    def test_names_returns_set(self):
        from pipeline.layouts import LayoutRegistry
        names = LayoutRegistry.names()
        assert isinstance(names, set)
        assert len(names) >= 1


class TestCTAContent:
    def test_valid_content(self):
        from pipeline.layouts.call_to_action import CTAContent
        c = CTAContent(
            takeaway="建议三个月内完成安全评估",
            action_items=["启动试点", "组建团队"],
        )
        assert c.takeaway == "建议三个月内完成安全评估"
        assert len(c.action_items) == 2

    def test_max_3_action_items(self):
        from pipeline.layouts.call_to_action import CTAContent
        with pytest.raises(pydantic.ValidationError):
            CTAContent(
                takeaway="X" * 10,
                action_items=["a", "b", "c", "d"],
            )

    def test_min_takeaway_length(self):
        from pipeline.layouts.call_to_action import CTAContent
        with pytest.raises(pydantic.ValidationError):
            CTAContent(takeaway="短")

    def test_empty_action_items_ok(self):
        from pipeline.layouts.call_to_action import CTAContent
        c = CTAContent(takeaway="这是一个足够长的核心结论句子")
        assert c.action_items == []

    def test_timeline_optional(self):
        from pipeline.layouts.call_to_action import CTAContent
        c = CTAContent(takeaway="核心结论足够长了", timeline="3-6 个月")
        assert c.timeline == "3-6 个月"


class TestCTABuildHtml:
    def _layout(self):
        from pipeline.layouts import LayoutRegistry
        return LayoutRegistry.get("call_to_action")

    def test_html_contains_takeaway(self):
        from pipeline.layouts.call_to_action import CTAContent
        layout = self._layout()
        content = CTAContent(
            takeaway="立即启动安全评估试点",
            action_items=["第一步：组建团队", "第二步：选场景"],
        )
        html = layout.build_html(content, {"primary": "#003D6E"}, 10, 10)
        assert "立即启动安全评估试点" in html
        assert "第一步：组建团队" in html
        assert "第二步：选场景" in html

    def test_html_uses_theme_colors(self):
        from pipeline.layouts.call_to_action import CTAContent
        layout = self._layout()
        content = CTAContent(takeaway="测试结论足够长了吧", action_items=["行动"])
        html = layout.build_html(content, {"primary": "#FF0000", "accent": "#00FF00"})
        assert "#FF0000" in html

    def test_no_dup_prefix_in_output(self):
        from pipeline.layer6_output.html_dup_check import detect_dup_prefix
        from pipeline.layouts.call_to_action import CTAContent
        layout = self._layout()
        content = CTAContent(
            takeaway="建议三个月内完成安全评估并启动两个核心场景试点",
            action_items=["组建专项团队"],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert detect_dup_prefix(html) is None

    def test_timeline_appears_when_set(self):
        from pipeline.layouts.call_to_action import CTAContent
        layout = self._layout()
        content = CTAContent(
            takeaway="核心结论句足够长的测试内容",
            action_items=["行动一"],
            timeline="3-6 个月",
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "3-6 个月" in html
        assert "建议时间窗" in html

    def test_no_timeline_when_empty(self):
        from pipeline.layouts.call_to_action import CTAContent
        layout = self._layout()
        content = CTAContent(
            takeaway="核心结论句足够长的测试内容",
            action_items=["行动一"],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "建议时间窗" not in html


class TestPlanAgentClosingLayout:
    def test_closing_slide_gets_call_to_action_hint(self):
        from pipeline.agents.plan_agent import PlanAgent
        agent = PlanAgent.__new__(PlanAgent)
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "title", "title": "T",
                 "section": "", "takeaway_message": "",
                 "primary_visual": "text_only", "narrative_arc": "opening"},
                {"page_number": 2, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence",
                 "takeaway_message": "First content slide takeaway sentence here",
                 "primary_visual": "text_only"},
                {"page_number": 3, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence",
                 "takeaway_message": "Last content slide closing takeaway sentence",
                 "primary_visual": "text_only"},
            ],
            "scqa": {"answer": "X"}, "root_claim": "X",
        }
        result = agent._to_outline_result(plan, scenario="季度汇报", framework_desc="SCR")
        content = [s for s in result["items"] if s.get("slide_type") == "content"]
        assert content[-1]["narrative_arc"] == "closing"
        assert content[-1]["layout_hint"] == "call_to_action"

    def test_non_closing_slides_unaffected(self):
        from pipeline.agents.plan_agent import PlanAgent
        agent = PlanAgent.__new__(PlanAgent)
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "title", "title": "T",
                 "section": "", "takeaway_message": "",
                 "primary_visual": "text_only", "narrative_arc": "opening"},
                {"page_number": 2, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence", "layout_hint": "metrics",
                 "takeaway_message": "First content slide takeaway sentence here",
                 "primary_visual": "text_only"},
                {"page_number": 3, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence", "layout_hint": "parallel_points",
                 "takeaway_message": "Last content slide closing takeaway sentence",
                 "primary_visual": "text_only"},
            ],
            "scqa": {"answer": "X"}, "root_claim": "X",
        }
        result = agent._to_outline_result(plan, scenario="季度汇报", framework_desc="SCR")
        content = [s for s in result["items"] if s.get("slide_type") == "content"]
        # First slide keeps its original layout_hint
        assert content[0]["layout_hint"] == "metrics"
        # Last slide gets overridden to call_to_action
        assert content[-1]["layout_hint"] == "call_to_action"
