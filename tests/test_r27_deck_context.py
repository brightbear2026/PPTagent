"""Tests for R27 — ContentAgent deck context window."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDeckContextWindow:
    def test_all_takeaways_populated_in_shared(self):
        """Verify _build_shared_context includes all_takeaways."""
        from unittest.mock import MagicMock
        from pipeline.agents.content_agent import ContentAgent

        agent = ContentAgent.__new__(ContentAgent)
        agent.llm = MagicMock()

        context = {
            "task": {"target_audience": "管理层"},
            "raw_content": {"source_pages": [], "_raw_text": "", "_tables": [], "_images": []},
            "analysis": {"strategy": {"core_themes": [], "key_messages": []}, "derived_metrics": [], "chunks": []},
            "outline": {
                "items": [
                    {"takeaway_message": "第一页论点"},
                    {"takeaway_message": "第二页论点"},
                    {"takeaway_message": "第三页论点"},
                ],
            },
        }
        shared = agent._build_shared_context(context)
        assert "all_takeaways" in shared
        assert len(shared["all_takeaways"]) == 3
        assert shared["all_takeaways"][0] == "第一页论点"

    def test_deck_dedup_context_in_prompt(self):
        """Verify deck dedup context appears in the built message."""
        from unittest.mock import MagicMock
        from pipeline.agents.content_agent import ContentAgent

        agent = ContentAgent.__new__(ContentAgent)
        agent.llm = MagicMock()

        slide = {
            "page_number": 3,
            "takeaway_message": "第三页论点",
            "primary_visual": "text_only",
            "slide_type": "content",
        }
        shared = {
            "task": {"target_audience": "管理层"},
            "tables": [],
            "source_pages": [],
            "chunks": [],
            "all_takeaways": ["第一页论点", "第二页论点", "第三页论点", "第四页论点"],
        }
        msgs = agent._build_slide_messages(slide, None, None, shared)
        user_msg = msgs[0].content

        assert "已讲过的论点" in user_msg
        assert "第一页论点" in user_msg
        assert "第二页论点" in user_msg

    def test_no_prev_takeaways_no_dedup(self):
        """First slide should have no dedup context."""
        from unittest.mock import MagicMock
        from pipeline.agents.content_agent import ContentAgent

        agent = ContentAgent.__new__(ContentAgent)
        agent.llm = MagicMock()

        slide = {"page_number": 1, "takeaway_message": "第一页", "primary_visual": "text_only"}
        shared = {
            "task": {"target_audience": "管理层"},
            "tables": [], "source_pages": [], "chunks": [],
            "all_takeaways": ["第一页"],
        }
        msgs = agent._build_slide_messages(slide, None, None, shared)
        assert "已讲过的论点" not in msgs[0].content
