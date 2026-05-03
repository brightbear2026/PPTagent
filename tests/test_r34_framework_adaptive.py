"""Tests for R34 — Framework adaptive selection."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestInferActualStructure:
    def test_report_structure(self):
        """≥4 H1 headings → report."""
        from pipeline.agents.analyze_agent import AnalyzeAgent

        raw = {
            "headings": [
                {"level": 1, "text": "第一章"},
                {"level": 1, "text": "第二章"},
                {"level": 1, "text": "第三章"},
                {"level": 1, "text": "第四章"},
            ],
        }
        assert AnalyzeAgent._infer_actual_structure(raw) == "report"

    def test_comparative_structure(self):
        """>3 tables → comparative."""
        from pipeline.agents.analyze_agent import AnalyzeAgent

        raw = {
            "headings": [{"level": 1, "text": "数据"}],
            "_tables": [{"headers": []}, {"headers": []}, {"headers": []}, {"headers": []}],
        }
        assert AnalyzeAgent._infer_actual_structure(raw) == "comparative"

    def test_narrative_few_headings(self):
        """≤1 H1 headings → narrative."""
        from pipeline.agents.analyze_agent import AnalyzeAgent

        raw = {
            "headings": [{"level": 1, "text": "仅一个标题"}],
        }
        assert AnalyzeAgent._infer_actual_structure(raw) == "narrative"

    def test_narrative_many_images(self):
        """≥3 images → narrative."""
        from pipeline.agents.analyze_agent import AnalyzeAgent

        raw = {
            "headings": [{"level": 1, "text": "A"}, {"level": 1, "text": "B"}],
            "structured_blocks": [
                {"type": "image"}, {"type": "image"}, {"type": "image"},
            ],
        }
        assert AnalyzeAgent._infer_actual_structure(raw) == "narrative"

    def test_tutorial_default(self):
        """2-3 H1, ≤3 tables, <3 images → tutorial."""
        from pipeline.agents.analyze_agent import AnalyzeAgent

        raw = {
            "headings": [{"level": 1, "text": "A"}, {"level": 1, "text": "B"}, {"level": 1, "text": "C"}],
        }
        assert AnalyzeAgent._infer_actual_structure(raw) == "tutorial"

    def test_empty_raw(self):
        """No data → narrative (fewest assumptions)."""
        from pipeline.agents.analyze_agent import AnalyzeAgent
        assert AnalyzeAgent._infer_actual_structure({}) == "narrative"


class TestPlanAgentStructurePrompt:
    def test_report_structure_note_in_prompt(self):
        """When actual_structure=report, prompt should contain structure hint."""
        from unittest.mock import MagicMock
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        agent.llm = MagicMock()
        prompt = agent._build_user_prompt(
            title="测试", scenario="季度汇报", target_audience="管理层",
            language="zh", analysis={"strategy": {}},
            chunks=[], raw={"source_pages": [], "_raw_text": ""},
            framework_arc="scr", actual_structure="report",
        )
        assert "报告结构" in prompt
        assert "章节划分" in prompt

    def test_comparative_structure_note_in_prompt(self):
        """When actual_structure=comparative, prompt mentions tables."""
        from unittest.mock import MagicMock
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        agent.llm = MagicMock()
        prompt = agent._build_user_prompt(
            title="测试", scenario="内部分析", target_audience="管理层",
            language="zh", analysis={"strategy": {}},
            chunks=[], raw={"source_pages": [], "_raw_text": ""},
            framework_arc="issue_tree", actual_structure="comparative",
        )
        assert "对比分析" in prompt or "表格" in prompt

    def test_no_structure_note_when_empty(self):
        """When actual_structure is empty, no structure hint."""
        from unittest.mock import MagicMock
        from pipeline.agents.plan_agent import PlanAgent

        agent = PlanAgent.__new__(PlanAgent)
        agent.llm = MagicMock()
        prompt = agent._build_user_prompt(
            title="测试", scenario="季度汇报", target_audience="管理层",
            language="zh", analysis={"strategy": {}},
            chunks=[], raw={"source_pages": [], "_raw_text": ""},
            framework_arc="scr", actual_structure="",
        )
        assert "文档结构提示" not in prompt
