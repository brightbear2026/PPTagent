"""
Regression test: PlanAgent must produce deterministic chapter numbering
regardless of what the LLM writes into content slides' `section` field.

Bug: LLM wrote "第一章 开篇导入" AND "第一章 背景与挑战" (both labeled
"第一章") into different content slides' section fields. _to_outline_result
collected unique section names verbatim, producing 6 section_divider slides
with chapter prefixes 一, 一, 二, 三, 四, 五 — off-by-one against the
deterministic sec_num used by section_divider HTML rendering.

Fix: strip any LLM-written "第X章 " prefix from section names, then
deterministic-number them by first-appearance order.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.agents.plan_agent import PlanAgent


def _make_agent():
    """PlanAgent constructor takes an LLM; for these unit tests we only call
    the pure helper / _to_outline_result, which doesn't actually call the LLM."""
    return PlanAgent.__new__(PlanAgent)  # bypass __init__


class TestChapterNumbering:
    def test_strip_chapter_prefix_helper(self):
        from pipeline.agents.plan_agent import _strip_chapter_prefix
        # Common LLM patterns
        assert _strip_chapter_prefix("第一章 开篇导入") == "开篇导入"
        assert _strip_chapter_prefix("第二章 背景与挑战") == "背景与挑战"
        assert _strip_chapter_prefix("第10章：技术细节") == "技术细节"
        assert _strip_chapter_prefix("第三章、风险全景") == "风险全景"
        # Already clean
        assert _strip_chapter_prefix("开篇导入") == "开篇导入"
        # Empty / weird
        assert _strip_chapter_prefix("") == ""
        assert _strip_chapter_prefix("第一章") == ""

    def test_deterministic_numbering_with_off_by_one_llm(self):
        """Reproduces the exact regression from outline_dump.json:
        LLM marked '开篇导入' AND '背景与挑战' both as '第一章'."""
        agent = _make_agent()

        # Mimic LLM output where chapter numbers are wrong
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "title", "title": "Report",
                 "section": "", "takeaway_message": "",
                 "primary_visual": "text_only", "narrative_arc": "opening"},
                {"page_number": 2, "slide_type": "content", "title": "Intro slide",
                 "section": "第一章 开篇导入",  # LLM wrote this
                 "takeaway_message": "Intro takeaway here is long enough",
                 "primary_visual": "text_only", "narrative_arc": "context"},
                {"page_number": 3, "slide_type": "content", "title": "Context slide",
                 "section": "第一章 背景与挑战",  # LLM ALSO wrote 第一章 — OFF BY ONE
                 "takeaway_message": "Context takeaway sentence describes the situation",
                 "primary_visual": "text_only", "narrative_arc": "evidence"},
                {"page_number": 4, "slide_type": "content", "title": "Risk slide",
                 "section": "第二章 风险全景",
                 "takeaway_message": "Risk takeaway sentence describes the risks involved",
                 "primary_visual": "text_only", "narrative_arc": "evidence"},
                {"page_number": 5, "slide_type": "content", "title": "Policy slide",
                 "section": "第三章 政策与合规要求",
                 "takeaway_message": "Policy takeaway sentence is also long enough here",
                 "primary_visual": "text_only", "narrative_arc": "evidence"},
            ],
            "scqa": {"answer": "Build proactive defense"},
            "root_claim": "Build proactive defense",
        }

        result = agent._to_outline_result(plan, scenario="季度汇报", framework_desc="SCR")

        # Find all section_divider slides — should be 4 (one per unique section)
        dividers = [s for s in result["items"] if s.get("slide_type") == "section_divider"]
        assert len(dividers) == 4, f"Expected 4 dividers, got {len(dividers)}: {[d.get('title') for d in dividers]}"

        # Each should have deterministic 第N章 prefix matching position
        expected_titles = ["第一章 开篇导入", "第二章 背景与挑战", "第三章 风险全景", "第四章 政策与合规要求"]
        actual_titles = [d["title"] for d in dividers]
        assert actual_titles == expected_titles, f"Got {actual_titles}"

        # Every divider's `section` field equals its `title` (single source of truth)
        for d in dividers:
            assert d["section"] == d["title"], f"section/title mismatch: {d}"

    def test_content_slide_section_normalized(self):
        """After fix, content slides should have stripped section names,
        so HTMLDesignAgent's _sections_list lookup is consistent."""
        agent = _make_agent()
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "title", "title": "T",
                 "section": "", "takeaway_message": "",
                 "primary_visual": "text_only", "narrative_arc": "opening"},
                {"page_number": 2, "slide_type": "content", "title": "A",
                 "section": "第一章 章A",  # with prefix
                 "takeaway_message": "Some takeaway sentence here for testing purposes",
                 "primary_visual": "text_only", "narrative_arc": "evidence"},
                {"page_number": 3, "slide_type": "content", "title": "B",
                 "section": "第二章 章B",
                 "takeaway_message": "Another takeaway sentence here for testing more",
                 "primary_visual": "text_only", "narrative_arc": "evidence"},
            ],
            "scqa": {"answer": "X"},
            "root_claim": "X",
        }
        result = agent._to_outline_result(plan, scenario="季度汇报", framework_desc="SCR")

        # Content slides' section field should match the canonical section_divider title
        content_slides = [s for s in result["items"] if s.get("slide_type") == "content"]
        dividers = [s for s in result["items"] if s.get("slide_type") == "section_divider"]

        divider_titles = {d["title"] for d in dividers}
        for cs in content_slides:
            assert cs["section"] in divider_titles, (
                f"Content slide section '{cs['section']}' has no matching divider in {divider_titles}"
            )

    def test_no_chapter_prefix_when_one_section(self):
        """Edge: if there's only 1 section, NO section_divider/agenda gets injected
        (existing behavior — line 542 `if len(sections_order) >= 2`)."""
        agent = _make_agent()
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "title", "title": "T",
                 "section": "", "takeaway_message": "",
                 "primary_visual": "text_only", "narrative_arc": "opening"},
                {"page_number": 2, "slide_type": "content", "title": "A",
                 "section": "唯一章节",
                 "takeaway_message": "Takeaway sentence for content slide A",
                 "primary_visual": "text_only", "narrative_arc": "evidence"},
            ],
            "scqa": {"answer": "X"},
            "root_claim": "X",
        }
        result = agent._to_outline_result(plan, scenario="季度汇报", framework_desc="SCR")
        dividers = [s for s in result["items"] if s.get("slide_type") == "section_divider"]
        assert len(dividers) == 0, "Single section should not inject divider"

    def test_more_than_ten_chapters(self):
        """Edge: chapter > 10 should fall back to digits."""
        from pipeline.agents.plan_agent import _strip_chapter_prefix, _chapter_label
        assert _chapter_label(1) == "一"
        assert _chapter_label(10) == "十"
        assert _chapter_label(11) == "11"
        assert _chapter_label(100) == "100"


class TestNarrativeArcEndpoints:
    def test_endpoints_have_deterministic_narrative_arc(self):
        agent = _make_agent()
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "title", "title": "T",
                 "section": "", "takeaway_message": "",
                 "primary_visual": "text_only", "narrative_arc": "opening"},
                {"page_number": 2, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence",  # LLM wrote wrong
                 "takeaway_message": "First content slide takeaway sentence here",
                 "primary_visual": "text_only"},
                {"page_number": 3, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence",
                 "takeaway_message": "Middle content slide takeaway sentence",
                 "primary_visual": "text_only"},
                {"page_number": 4, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence",  # LLM wrote wrong
                 "takeaway_message": "Last content slide closing takeaway sentence",
                 "primary_visual": "text_only"},
            ],
            "scqa": {"answer": "X"}, "root_claim": "X",
        }
        result = agent._to_outline_result(plan, scenario="季度汇报", framework_desc="SCR")
        content = [s for s in result["items"] if s.get("slide_type") == "content"]
        assert content[0]["narrative_arc"] == "opening"
        assert content[-1]["narrative_arc"] == "closing"
        # Middle slides untouched
        for s in content[1:-1]:
            assert s["narrative_arc"] == "evidence"

    def test_single_content_slide_gets_both(self):
        """Edge: if there's only 1 content slide, it gets opening+closing."""
        agent = _make_agent()
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "title", "title": "T",
                 "section": "", "takeaway_message": "",
                 "primary_visual": "text_only", "narrative_arc": "opening"},
                {"page_number": 2, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence",
                 "takeaway_message": "The only content slide takeaway sentence",
                 "primary_visual": "text_only"},
            ],
            "scqa": {"answer": "X"}, "root_claim": "X",
        }
        result = agent._to_outline_result(plan, scenario="季度汇报", framework_desc="SCR")
        content = [s for s in result["items"] if s.get("slide_type") == "content"]
        assert len(content) == 1
        assert content[0]["narrative_arc"] == "closing"  # last write wins


class TestSectionPageBalance:

    def test_verify_plan_flags_thin_chapter(self):
        agent = _make_agent()
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "title"},
                {"page_number": 2, "slide_type": "content", "section": "Ch1",
                 "takeaway_message": "Sole content sentence", "primary_visual": "text_only"},
                {"page_number": 3, "slide_type": "content", "section": "Ch2",
                 "takeaway_message": "Another content sentence here", "primary_visual": "text_only"},
                {"page_number": 4, "slide_type": "content", "section": "Ch2",
                 "takeaway_message": "Yet another sentence in Ch2", "primary_visual": "text_only"},
            ],
            "scqa": {"answer": "X"},
        }
        issues = agent._verify_plan(plan, [], "scr")
        assert any("Ch1" in i and "偏薄" in i for i in issues)

    def test_verify_plan_flags_overlong_chapter(self):
        # 9 slides in one section
        plan = {
            "slides": [{"page_number": 1, "slide_type": "title"}] + [
                {"page_number": i + 2, "slide_type": "content", "section": "Big",
                 "takeaway_message": f"Slide {i} content", "primary_visual": "text_only"}
                for i in range(9)
            ],
            "scqa": {"answer": "X"},
        }
        agent = _make_agent()
        issues = agent._verify_plan(plan, [], "scr")
        assert any("Big" in i and "过详" in i for i in issues)

    def test_balanced_chapters_no_flag(self):
        agent = _make_agent()
        plan = {
            "slides": [{"page_number": 1, "slide_type": "title"}] + [
                {"page_number": i + 2, "slide_type": "content", "section": "Balanced",
                 "takeaway_message": f"Slide {i} content here", "primary_visual": "text_only"}
                for i in range(4)
            ],
            "scqa": {"answer": "X"},
        }
        issues = agent._verify_plan(plan, [], "scr")
        assert not any("偏薄" in i or "过详" in i for i in issues)
