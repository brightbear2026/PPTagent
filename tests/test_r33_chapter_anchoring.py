"""Tests for R33 — PlanAgent chapter name anchoring to source headings."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAnchorChapterNames:
    def test_fuzzy_match_replaces_similar_name(self):
        """LLM '市场分析概览' should anchor to source '市场分析'."""
        from pipeline.agents.plan_agent import PlanAgent

        slides = [
            {"slide_type": "content", "section": "市场分析概览"},
            {"slide_type": "content", "section": "风险评估与控制"},
        ]
        source_h1 = ["市场分析", "风险评估", "总结"]
        PlanAgent._anchor_chapter_names(slides, source_h1)
        assert slides[0]["section"] == "市场分析"
        assert slides[1]["section"] == "风险评估"

    def test_no_match_keeps_original(self):
        """When no source heading is similar, keep the LLM name."""
        from pipeline.agents.plan_agent import PlanAgent

        slides = [
            {"slide_type": "content", "section": "量子物理导论"},
        ]
        source_h1 = ["市场分析", "风险评估"]
        PlanAgent._anchor_chapter_names(slides, source_h1)
        assert slides[0]["section"] == "量子物理导论"

    def test_empty_source_no_change(self):
        """Empty source headings list means no anchoring."""
        from pipeline.agents.plan_agent import PlanAgent

        slides = [
            {"slide_type": "content", "section": "市场分析"},
        ]
        PlanAgent._anchor_chapter_names(slides, [])
        assert slides[0]["section"] == "市场分析"

    def test_title_and_agenda_skipped(self):
        """Title and agenda slides should not be modified."""
        from pipeline.agents.plan_agent import PlanAgent

        slides = [
            {"slide_type": "title", "section": "封面"},
            {"slide_type": "agenda", "section": ""},
            {"slide_type": "content", "section": "市场分析概览"},
        ]
        source_h1 = ["市场分析"]
        PlanAgent._anchor_chapter_names(slides, source_h1)
        assert slides[0]["section"] == "封面"
        assert slides[2]["section"] == "市场分析"

    def test_exact_match_unchanged(self):
        """When LLM name exactly matches a source heading, no change needed."""
        from pipeline.agents.plan_agent import PlanAgent

        slides = [
            {"slide_type": "content", "section": "市场分析"},
        ]
        source_h1 = ["市场分析", "风险评估"]
        PlanAgent._anchor_chapter_names(slides, source_h1)
        assert slides[0]["section"] == "市场分析"

    def test_integration_with_to_outline_result(self):
        """Verify anchoring happens inside _to_outline_result."""
        from pipeline.agents.plan_agent import PlanAgent

        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "content",
                 "takeaway_message": "T1", "section": "市场分析概览",
                 "primary_visual": "text_only"},
                {"page_number": 2, "slide_type": "content",
                 "takeaway_message": "T2", "section": "风险评估与应对",
                 "primary_visual": "text_only"},
            ],
            "scqa": {},
        }
        agent = PlanAgent.__new__(PlanAgent)
        result = agent._to_outline_result(
            plan, "季度汇报", "SCR",
            chunks=None,
            source_h1_texts=["市场分析", "风险评估", "总结与展望"],
        )
        items = result["items"]
        # section_divider slides should use anchored names
        divider_sections = [
            s["section"] for s in items
            if s.get("slide_type") == "section_divider"
        ]
        # At least one section_divider should contain anchored name
        assert any("市场分析" in s for s in divider_sections)
