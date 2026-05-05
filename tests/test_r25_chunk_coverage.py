"""Tests for R25 — PlanAgent chunks 100% coverage."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestEnsureChunkCoverage:
    def test_all_covered_no_expansion(self):
        from pipeline.agents.plan_agent import PlanAgent
        agent = PlanAgent.__new__(PlanAgent)
        result = {
            "items": [
                {"page_number": 1, "slide_type": "content", "chunk_ids": ["c1", "c2"],
                 "takeaway_message": "Slide 1", "title": "S1"},
            ],
        }
        chunks = [
            {"id": "c1", "text": "Chunk 1"},
            {"id": "c2", "text": "Chunk 2"},
        ]
        new_result = agent._ensure_chunk_coverage(result, chunks)
        assert len(new_result["items"]) == 1

    def test_uncovered_chunks_get_expansion_slides(self):
        from pipeline.agents.plan_agent import PlanAgent
        agent = PlanAgent.__new__(PlanAgent)
        result = {
            "items": [
                {"page_number": 1, "slide_type": "content", "chunk_ids": ["c1"],
                 "takeaway_message": "S1", "title": "S1", "section": "Ch1"},
                {"page_number": 2, "slide_type": "section_divider", "chunk_ids": [],
                 "takeaway_message": "S2", "title": "S2", "section": "Ch2"},
            ],
        }
        chunks = [
            {"id": "c1", "text": "Covered chunk"},
            {"id": "c2", "text": "Uncovered chunk A", "section": "Ch1"},
            {"id": "c3", "text": "Uncovered chunk B", "section": "Ch2"},
        ]
        new_result = agent._ensure_chunk_coverage(result, chunks)
        assert len(new_result["items"]) == 4  # 2 original + 2 expansion

        # Expansion slides should have the right chunk_ids
        expansion = [s for s in new_result["items"] if "c2" in s.get("chunk_ids", [])]
        assert len(expansion) == 1

    def test_page_numbers_renumbered(self):
        from pipeline.agents.plan_agent import PlanAgent
        agent = PlanAgent.__new__(PlanAgent)
        result = {
            "items": [
                {"page_number": 1, "slide_type": "section_divider", "chunk_ids": [],
                 "takeaway_message": "S1", "title": "S1", "section": "Ch1"},
                {"page_number": 2, "slide_type": "content", "chunk_ids": ["c1"],
                 "takeaway_message": "S1", "title": "S1", "section": "Ch1"},
            ],
        }
        chunks = [
            {"id": "c1", "text": "Covered"},
            {"id": "c2", "text": "Uncovered with section", "section": "Ch1"},
        ]
        new_result = agent._ensure_chunk_coverage(result, chunks)
        pages = [s["page_number"] for s in new_result["items"]]
        assert pages == [1, 2, 3]

    def test_empty_chunks_no_change(self):
        from pipeline.agents.plan_agent import PlanAgent
        agent = PlanAgent.__new__(PlanAgent)
        result = {"items": [{"page_number": 1, "chunk_ids": []}]}
        new_result = agent._ensure_chunk_coverage(result, [])
        assert len(new_result["items"]) == 1

    def test_typed_chunks_with_heading_path(self):
        from pipeline.agents.plan_agent import PlanAgent
        agent = PlanAgent.__new__(PlanAgent)
        result = {
            "items": [
                {"page_number": 1, "slide_type": "section_divider", "chunk_ids": [],
                 "takeaway_message": "S1", "title": "1.2", "section": "1.2"},
                {"page_number": 2, "slide_type": "content", "chunk_ids": ["c1"],
                 "takeaway_message": "S1", "title": "S1", "section": "1.2"},
            ],
        }
        chunks = [
            {"id": "c1", "text": "Covered", "type": "text"},
            {"id": "c2", "text": "Table data", "type": "table", "heading_path": ["第一章", "1.2"]},
        ]
        new_result = agent._ensure_chunk_coverage(result, chunks)
        expansion = [s for s in new_result["items"] if "c2" in s.get("chunk_ids", [])]
        assert len(expansion) == 1
