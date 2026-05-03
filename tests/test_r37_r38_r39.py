"""Tests for R37 (threshold 7) + R38 (in-chapter expansion) + R39 (orphan assignment)."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestR37Threshold:
    def test_seven_slides_triggers_warning(self):
        """A chapter with 7 content slides should trigger overlong warning."""
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        plan = {
            "slides": [
                {"slide_type": "content", "section": "长章节",
                 "takeaway_message": f"论点{i}", "narrative_arc": "evidence"}
                for i in range(7)
            ],
            "scqa": {},
        }
        issues = agent._verify_plan(plan, [], "scqa", 10000)
        assert any("7 页" in iss and "偏多" in iss for iss in issues)

    def test_six_slides_no_warning(self):
        """A chapter with 6 content slides should NOT trigger warning."""
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        plan = {
            "slides": [
                {"slide_type": "content", "section": "正常章节",
                 "takeaway_message": f"论点{i}", "narrative_arc": "evidence"}
                for i in range(6)
            ],
            "scqa": {},
        }
        issues = agent._verify_plan(plan, [], "scqa", 10000)
        assert not any("偏多" in iss for iss in issues)


class TestR38InChapterExpansion:
    def test_expansion_inserted_before_next_chapter(self):
        """Expansion slide for chapter 1 should appear before chapter 2 divider."""
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        result = {
            "items": [
                {"page_number": 1, "slide_type": "title", "section": "",
                 "takeaway_message": "", "chunk_ids": []},
                {"page_number": 2, "slide_type": "section_divider", "section": "第一章 A",
                 "takeaway_message": "第一章 A", "chunk_ids": []},
                {"page_number": 3, "slide_type": "content", "section": "第一章 A",
                 "takeaway_message": "S1", "chunk_ids": ["c1"]},
                {"page_number": 4, "slide_type": "section_divider", "section": "第二章 B",
                 "takeaway_message": "第二章 B", "chunk_ids": []},
                {"page_number": 5, "slide_type": "content", "section": "第二章 B",
                 "takeaway_message": "S2", "chunk_ids": ["c2"]},
            ],
        }
        chunks = [
            {"id": "c1", "text": "Covered", "section": "A"},
            {"id": "c2", "text": "Covered2", "section": "B"},
            {"id": "c3", "text": "Uncovered in chapter A", "section": "A"},
        ]
        new_result = agent._ensure_chunk_coverage(result, chunks)
        items = new_result["items"]
        # Find the expansion slide
        expansion = [s for s in items if "c3" in s.get("chunk_ids", [])]
        assert len(expansion) == 1
        # It should be BEFORE the second section_divider
        exp_idx = items.index(expansion[0])
        div2 = [i for i, s in enumerate(items) if s.get("slide_type") == "section_divider"]
        assert len(div2) == 2
        assert exp_idx < div2[1], "Expansion for ch1 must appear before ch2 divider"

    def test_expansion_not_at_end(self):
        """Expansion slides should NOT be appended at the end of the deck."""
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        result = {
            "items": [
                {"page_number": 1, "slide_type": "section_divider", "section": "第一章 A",
                 "takeaway_message": "A", "chunk_ids": []},
                {"page_number": 2, "slide_type": "content", "section": "第一章 A",
                 "takeaway_message": "S1", "chunk_ids": ["c1"]},
                {"page_number": 3, "slide_type": "section_divider", "section": "第二章 B",
                 "takeaway_message": "B", "chunk_ids": []},
                {"page_number": 4, "slide_type": "content", "section": "第二章 B",
                 "takeaway_message": "S2", "chunk_ids": []},
            ],
        }
        chunks = [
            {"id": "c1", "text": "C1", "section": "A"},
            {"id": "c3", "text": "Uncovered in A", "section": "A"},
        ]
        new_result = agent._ensure_chunk_coverage(result, chunks)
        items = new_result["items"]
        expansion = [s for s in items if "c3" in s.get("chunk_ids", [])]
        assert len(expansion) == 1
        # Not the last item
        assert items[-1] != expansion[0]


class TestR39OrphanAssignment:
    def test_orphan_assigned_to_preceding_chapter(self):
        """Content slides with section="" should inherit nearest preceding chapter."""
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "content", "section": "市场分析",
                 "takeaway_message": "S1", "primary_visual": "text_only"},
                {"page_number": 2, "slide_type": "content", "section": "",
                 "takeaway_message": "S2", "primary_visual": "text_only"},
                {"page_number": 3, "slide_type": "content", "section": "风险评估",
                 "takeaway_message": "S3", "primary_visual": "text_only"},
                {"page_number": 4, "slide_type": "content", "section": "",
                 "takeaway_message": "S4", "primary_visual": "text_only"},
            ],
            "scqa": {},
        }
        result = agent._to_outline_result(plan, "季度汇报", "SCR", chunks=None)
        items = result["items"]
        # Orphan slide S2 should be under 市场分析 chapter
        s2 = next(s for s in items if s.get("takeaway_message") == "S2")
        assert s2["section"] != "", "Orphan slide should be assigned to a chapter"
        # S4 should be under 风险评估 chapter
        s4 = next(s for s in items if s.get("takeaway_message") == "S4")
        assert s4["section"] != "", "Orphan slide should be assigned to a chapter"
