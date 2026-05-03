"""Tests for R36 — Framework-chapter mapping backend."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestNarrativeArcMapping:
    def test_all_six_frameworks_present(self):
        from pipeline.agents.plan_agent import NARRATIVE_ARC_TO_FRAMEWORK_KEY
        assert set(NARRATIVE_ARC_TO_FRAMEWORK_KEY.keys()) == {
            "scqa", "scr", "aida", "explanation", "issue_tree", "problem_solution",
        }

    def test_scqa_evidence_maps_to_complication(self):
        from pipeline.agents.plan_agent import NARRATIVE_ARC_TO_FRAMEWORK_KEY
        assert NARRATIVE_ARC_TO_FRAMEWORK_KEY["scqa"]["evidence"] == "complication"


class TestComputeFrameworkChapterMap:
    def _make_agent(self):
        from pipeline.agents.plan_agent import PlanAgent
        return PlanAgent.__new__(PlanAgent)

    def test_basic_scqa_three_chapters(self):
        agent = self._make_agent()
        slides = [
            {"slide_type": "title", "narrative_arc": "opening"},
            {"slide_type": "section_divider", "section": "Ch1"},
            {"slide_type": "content", "narrative_arc": "opening"},
            {"slide_type": "content", "narrative_arc": "opening"},
            {"slide_type": "section_divider", "section": "Ch2"},
            {"slide_type": "content", "narrative_arc": "evidence"},
            {"slide_type": "content", "narrative_arc": "context"},
            {"slide_type": "section_divider", "section": "Ch3"},
            {"slide_type": "content", "narrative_arc": "solution"},
            {"slide_type": "content", "narrative_arc": "recommendation"},
        ]
        result = agent._compute_framework_chapter_map(slides, "scqa")
        # Ch1 (opening→situation), Ch2 (evidence+context→complication), Ch3 (solution→answer)
        assert result["situation"] == "第一章"
        assert result["complication"] == "第二章"
        assert result["answer"] == "第三章"

    def test_merged_chapters_discrete_list(self):
        """Multiple chapters in same phase get discrete list, not '到' range."""
        agent = self._make_agent()
        slides = [
            {"slide_type": "section_divider", "section": "Ch1"},
            {"slide_type": "content", "narrative_arc": "evidence"},
            {"slide_type": "content", "narrative_arc": "evidence"},
            {"slide_type": "section_divider", "section": "Ch2"},
            {"slide_type": "content", "narrative_arc": "evidence"},
            {"slide_type": "section_divider", "section": "Ch3"},
            {"slide_type": "content", "narrative_arc": "solution"},
        ]
        result = agent._compute_framework_chapter_map(slides, "scqa")
        # Ch1+Ch2 both complication, Ch3 answer
        assert "第一章" in result["complication"]
        assert "第二章" in result["complication"]
        assert "到" not in result["complication"]  # discrete list, no "到"
        assert result["answer"] == "第三章"

    def test_tie_break_first_non_opening(self):
        """When tied, prefer first non-opening arc."""
        agent = self._make_agent()
        slides = [
            {"slide_type": "section_divider", "section": "Ch1"},
            {"slide_type": "content", "narrative_arc": "opening"},
            {"slide_type": "content", "narrative_arc": "evidence"},
        ]
        result = agent._compute_framework_chapter_map(slides, "scqa")
        # opening→situation, evidence→complication — tie, first non-opening=complication
        assert result.get("complication") == "第一章"

    def test_unknown_framework_returns_empty(self):
        agent = self._make_agent()
        slides = [{"slide_type": "section_divider", "section": "Ch1"}]
        result = agent._compute_framework_chapter_map(slides, "nonexistent")
        assert result == {}


class TestFrameworkPhaseAnnotation:
    def test_section_dividers_get_framework_phase(self):
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        plan = {
            "slides": [
                {"slide_type": "content", "section": "背景",
                 "takeaway_message": "S1", "narrative_arc": "opening"},
                {"slide_type": "content", "section": "挑战",
                 "takeaway_message": "S2", "narrative_arc": "evidence"},
                {"slide_type": "content", "section": "方案",
                 "takeaway_message": "S3", "narrative_arc": "solution"},
            ],
            "scqa": {"situation": "S", "complication": "C", "answer": "A"},
        }
        result = agent._to_outline_result(plan, "战略提案", "SCQA框架")
        items = result["items"]
        dividers = [s for s in items if s.get("slide_type") == "section_divider"]
        # Each divider should have a framework_phase
        for d in dividers:
            assert "framework_phase" in d, f"Divider '{d.get('title')}' missing framework_phase"

    def test_framework_chapter_map_in_result(self):
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        plan = {
            "slides": [
                {"slide_type": "content", "section": "背景",
                 "takeaway_message": "S1", "narrative_arc": "opening"},
                {"slide_type": "content", "section": "挑战",
                 "takeaway_message": "S2", "narrative_arc": "evidence"},
            ],
            "scqa": {},
        }
        result = agent._to_outline_result(plan, "战略提案", "SCQA框架")
        assert "framework_chapter_map" in result
        assert isinstance(result["framework_chapter_map"], dict)
