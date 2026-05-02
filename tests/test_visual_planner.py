"""Tests for VisualPlannerAgent and VisualPlan schema."""
import pytest
from pydantic import ValidationError


class TestVisualPlanSchema:
    def test_valid_plan_passes(self):
        from models.visual_plan_schema import VisualPlan
        plan = VisualPlan(
            page_number=5,
            layout_id="parallel_points",
            layout_content={"title": "测试标题", "bullets": ["论据1", "论据2", "论据3", "论据4"]},
            rationale="四条并列论据适合使用 parallel_points 布局",
            confidence=0.9,
        )
        assert plan.layout_id == "parallel_points"

    def test_invalid_layout_id_rejected(self):
        from models.visual_plan_schema import VisualPlan
        with pytest.raises(ValidationError, match="Unknown layout_id"):
            VisualPlan(
                page_number=1,
                layout_id="nonexistent_layout",
                layout_content={},
                rationale="测试未知 layout",
            )

    def test_invalid_layout_content_rejected(self):
        from models.visual_plan_schema import VisualPlan
        with pytest.raises(ValidationError):
            VisualPlan(
                page_number=1,
                layout_id="parallel_points",
                layout_content={"title": "测试", "bullets": ["仅一条"]},
                rationale="内容不满足 schema（bullets 太少，需要4-6条）",
            )

    def test_rationale_too_short_rejected(self):
        from models.visual_plan_schema import VisualPlan
        with pytest.raises(ValidationError, match="rationale"):
            VisualPlan(
                page_number=1,
                layout_id="parallel_points",
                layout_content={"title": "测试", "bullets": ["a", "b", "c", "d"]},
                rationale="太短",
            )

    def test_confidence_bounds(self):
        from models.visual_plan_schema import VisualPlan
        with pytest.raises(ValidationError):
            VisualPlan(
                page_number=1,
                layout_id="framework_grid",
                layout_content={"title": "测试", "items": [
                    {"icon": "📊", "title": "模块1", "desc": "描述"},
                ]},
                rationale="测试 confidence 越界",
                confidence=1.5,
            )

    def test_visual_plan_result(self):
        from models.visual_plan_schema import VisualPlanResult
        result = VisualPlanResult(
            plans=[],
            fallback_pages=[3, 7],
        )
        assert result.fallback_pages == [3, 7]


class TestVisualPlanJsonParsing:
    def test_parse_fenced_json(self):
        from pipeline.agents.visual_planner_agent import VisualPlannerAgent
        text = '```json\n{"page_number": 1, "layout_id": "parallel_points", "layout_content": {"title": "测试", "bullets": ["a","b","c","d"]}, "rationale": "理由充分的解释文本"}\n```'
        result = VisualPlannerAgent._parse_json(text)
        assert result is not None
        assert result["layout_id"] == "parallel_points"

    def test_parse_raw_json(self):
        from pipeline.agents.visual_planner_agent import VisualPlannerAgent
        text = '{"page_number": 1, "layout_id": "metrics", "layout_content": {"title": "指标", "metrics": [{"label": "用户", "value": "100万", "unit": "人", "description": "月活用户"}]}, "rationale": "页面包含多个关键指标"}'
        result = VisualPlannerAgent._parse_json(text)
        assert result is not None
        assert result["layout_id"] == "metrics"

    def test_parse_no_json_returns_none(self):
        from pipeline.agents.visual_planner_agent import VisualPlannerAgent
        result = VisualPlannerAgent._parse_json("这是普通文本没有 JSON")
        assert result is None


class TestDiversityEnforcement:
    def test_three_consecutive_replaced(self):
        from pipeline.agents.visual_planner_agent import VisualPlannerAgent
        agent = VisualPlannerAgent.__new__(VisualPlannerAgent)
        results = {
            1: {"layout_id": "parallel_points", "page_number": 1},
            2: {"layout_id": "parallel_points", "page_number": 2},
            3: {"layout_id": "parallel_points", "page_number": 3},
        }
        slides = [
            {"page_number": 1, "takeaway_message": "测试1", "text_blocks": [{"content": f"论据{i}", "level": 1} for i in range(5)]},
            {"page_number": 2, "takeaway_message": "测试2", "text_blocks": [{"content": f"论据{i}", "level": 1} for i in range(5)]},
            {"page_number": 3, "takeaway_message": "测试3", "text_blocks": [{"content": f"论据{i}", "level": 1} for i in range(5)]},
        ]
        new_results = agent._enforce_diversity(results, slides, "")
        assert new_results[3]["layout_id"] != "parallel_points"

    def test_two_consecutive_allowed(self):
        from pipeline.agents.visual_planner_agent import VisualPlannerAgent
        agent = VisualPlannerAgent.__new__(VisualPlannerAgent)
        results = {
            1: {"layout_id": "parallel_points", "page_number": 1},
            2: {"layout_id": "parallel_points", "page_number": 2},
            3: {"layout_id": "framework_grid", "page_number": 3},
        }
        slides = [
            {"page_number": 1, "takeaway_message": "测试1", "text_blocks": [{"content": "论据", "level": 1}]},
            {"page_number": 2, "takeaway_message": "测试2", "text_blocks": [{"content": "论据", "level": 1}]},
            {"page_number": 3, "takeaway_message": "测试3", "text_blocks": [{"content": "论据", "level": 1}]},
        ]
        new_results = agent._enforce_diversity(results, slides, "")
        assert new_results[3]["layout_id"] == "framework_grid"


class TestNeighborExcludes:
    def test_two_same_previous_excludes(self):
        from pipeline.agents.visual_planner_agent import VisualPlannerAgent
        agent = VisualPlannerAgent.__new__(VisualPlannerAgent)
        neighbor_plans = {1: "parallel_points", 2: "parallel_points"}
        excludes = agent._neighbor_excludes(neighbor_plans, 3, [])
        assert "parallel_points" in excludes

    def test_different_previous_no_exclude(self):
        from pipeline.agents.visual_planner_agent import VisualPlannerAgent
        agent = VisualPlannerAgent.__new__(VisualPlannerAgent)
        neighbor_plans = {1: "parallel_points", 2: "framework_grid"}
        excludes = agent._neighbor_excludes(neighbor_plans, 3, [])
        assert len(excludes) == 0
