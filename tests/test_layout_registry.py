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

    def test_registry_has_quote_emphasis(self):
        from pipeline.layouts import LayoutRegistry
        assert "quote_emphasis" in LayoutRegistry.names()

    def test_registry_get_returns_layout(self):
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("call_to_action")
        assert layout.name == "call_to_action"
        layout2 = LayoutRegistry.get("quote_emphasis")
        assert layout2.name == "quote_emphasis"

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
            action_items=["启动试点", "组建团队", "选定场景"],
            timeline="3-6个月",
        )
        assert c.takeaway == "建议三个月内完成安全评估"
        assert len(c.action_items) == 3

    def test_max_5_action_items(self):
        from pipeline.layouts.call_to_action import CTAContent
        with pytest.raises(pydantic.ValidationError):
            CTAContent(
                takeaway="X" * 10,
                action_items=["a", "b", "c", "d", "e", "f"],
                timeline="1个月",
            )

    def test_min_takeaway_length(self):
        from pipeline.layouts.call_to_action import CTAContent
        with pytest.raises(pydantic.ValidationError):
            CTAContent(takeaway="短", action_items=["a", "b", "c"], timeline="t")

    def test_min_3_action_items(self):
        from pipeline.layouts.call_to_action import CTAContent
        with pytest.raises(pydantic.ValidationError):
            CTAContent(takeaway="足够长的核心结论句子", action_items=["a"], timeline="t")

    def test_timeline_required(self):
        from pipeline.layouts.call_to_action import CTAContent
        with pytest.raises(pydantic.ValidationError):
            CTAContent(takeaway="核心结论足够长了", action_items=["a", "b", "c"])

    def test_reject_duplicated_action_item(self):
        from pipeline.layouts.call_to_action import CTAContent
        with pytest.raises(pydantic.ValidationError, match="duplicates takeaway"):
            CTAContent(
                takeaway="头部金融科技公司已部署AI红队和模型防火墙",
                action_items=["头部金融科技公司已部署AI红队", "b", "c"],
                timeline="1个月",
            )


class TestCTABuildHtml:
    def _layout(self):
        from pipeline.layouts import LayoutRegistry
        return LayoutRegistry.get("call_to_action")

    def _content(self, **overrides):
        from pipeline.layouts.call_to_action import CTAContent
        defaults = dict(
            takeaway="立即启动安全评估试点",
            action_items=["第一步：组建团队", "第二步：选场景", "第三步：评估"],
            timeline="3-6个月",
        )
        defaults.update(overrides)
        return CTAContent(**defaults)

    def test_html_contains_takeaway(self):
        layout = self._layout()
        content = self._content()
        html = layout.build_html(content, {"primary": "#003D6E"}, 10, 10)
        assert "立即启动安全评估试点" in html
        assert "第一步：组建团队" in html
        assert "第三步：评估" in html

    def test_html_has_footer(self):
        layout = self._layout()
        content = self._content()
        html = layout.build_html(content, {"primary": "#003D6E"}, 5, 20)
        assert "P5 / 20" in html

    def test_html_uses_theme_colors(self):
        layout = self._layout()
        content = self._content()
        html = layout.build_html(content, {"primary": "#FF0000", "accent": "#00FF00"})
        assert "#FF0000" in html

    def test_no_dup_prefix_in_output(self):
        from pipeline.layer6_output.html_dup_check import detect_dup_prefix
        layout = self._layout()
        content = self._content()
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert detect_dup_prefix(html) is None

    def test_timeline_appears(self):
        layout = self._layout()
        content = self._content(timeline="3-6 个月")
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "3-6 个月" in html
        assert "建议时间窗" in html


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


class TestQuoteEmphasisLayout:
    def _layout(self):
        from pipeline.layouts import LayoutRegistry
        return LayoutRegistry.get("quote_emphasis")

    def test_from_slide_data(self):
        layout = self._layout()
        slide_data = {
            "takeaway_message": "核心论点足够长的测试句子",
            "text_blocks": [
                {"type": "heading", "content": "标题"},
                {"type": "bullet", "content": "这是第一个核心结论作为引用文本", "level": 1},
                {"type": "bullet", "content": "这是第二个支撑论据的详细描述", "level": 1},
                {"type": "bullet", "content": "这是第三个支撑论据的更多细节", "level": 1},
            ],
        }
        content = layout.from_slide_data(slide_data)
        assert "引用文本" in content.quote_text
        assert len(content.sub_bullets) == 2

    def test_build_html_contains_quote(self):
        from pipeline.layouts.quote_emphasis import QuoteEmphasisContent
        layout = self._layout()
        content = QuoteEmphasisContent(
            title="测试标题足够长了",
            quote_text="这是一个非常重要的核心结论值得强调",
            sub_bullets=["支撑论据一", "支撑论据二"],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "非常重要的核心结论" in html
        assert "支撑论据一" in html

    def test_no_dup_prefix(self):
        from pipeline.layer6_output.html_dup_check import detect_dup_prefix
        from pipeline.layouts.quote_emphasis import QuoteEmphasisContent
        layout = self._layout()
        content = QuoteEmphasisContent(
            title="测试标题足够长的句子内容",
            quote_text="核心结论引用文本内容也足够长",
            sub_bullets=["论据一描述", "论据二描述"],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert detect_dup_prefix(html) is None

    def test_fallback_to_takeaway_when_no_blocks(self):
        layout = self._layout()
        slide_data = {
            "takeaway_message": "当没有text_blocks时使用takeaway作为引用",
            "text_blocks": [],
        }
        content = layout.from_slide_data(slide_data)
        assert "takeaway" in content.quote_text or "使用takeaway" in content.quote_text
