"""Tests for registry-typed comparison, framework_grid, narrative layouts."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestRegistryComplete:
    def test_all_eight_registered(self):
        from pipeline.layouts import LayoutRegistry
        expected = {
            "call_to_action", "quote_emphasis", "parallel_points",
            "metrics", "chart_focus", "comparison",
            "framework_grid", "narrative",
            "tech_architecture", "capability_matrix", "case_study",
            "solution_comparison", "end_to_end_flow",
            "image_text_grid",
        }
        assert LayoutRegistry.names() == expected


class TestComparisonLayout:
    def test_from_slide_data_vblock(self):
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("comparison")
        sd = {
            "takeaway_message": "对比两种方案的优劣",
            "text_blocks": [],
            "visual_block": {
                "type": "comparison_columns",
                "items": [
                    {"title": "方案A优点一"}, {"title": "方案A优点二"},
                    {"title": "方案B优点一"}, {"title": "方案B优点二"},
                ],
            },
        }
        content = layout.from_slide_data(sd)
        assert len(content.left_bullets) == 2
        assert len(content.right_bullets) == 2

    def test_build_html(self):
        from pipeline.layouts.comparison import ComparisonContent
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("comparison")
        content = ComparisonContent(
            title="方案对比",
            left_label="方案A",
            left_bullets=["优点一", "优点二"],
            right_label="方案B",
            right_bullets=["优点一", "优点二"],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "方案A" in html
        assert "方案B" in html


class TestFrameworkGridLayout:
    def test_from_slide_data_vblock(self):
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("framework_grid")
        sd = {
            "takeaway_message": "四大核心能力框架",
            "text_blocks": [],
            "visual_block": {
                "type": "icon_text_grid",
                "items": [
                    {"title": "能力一", "description": "描述一"},
                    {"title": "能力二", "description": "描述二"},
                    {"title": "能力三", "description": "描述三"},
                ],
            },
        }
        content = layout.from_slide_data(sd)
        assert len(content.items) == 3
        assert content.items[0].title == "能力一"

    def test_build_html(self):
        from pipeline.layouts.framework_grid import FrameworkGridContent, GridItem
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("framework_grid")
        content = FrameworkGridContent(
            title="核心框架",
            items=[
                GridItem(icon="🎯", title="维度一", desc="描述内容"),
                GridItem(icon="📊", title="维度二", desc="描述内容"),
            ],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "维度一" in html
        assert "🎯" in html


class TestNarrativeLayout:
    def test_from_slide_data_vblock(self):
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("narrative")
        sd = {
            "takeaway_message": "三阶段实施路径清晰可行",
            "text_blocks": [],
            "visual_block": {
                "type": "step_cards",
                "items": [
                    {"label": "30天", "title": "快速验证", "description": "MVP上线"},
                    {"label": "90天", "title": "规模扩展", "description": "全量推广"},
                ],
            },
        }
        content = layout.from_slide_data(sd)
        assert len(content.phases) == 2
        assert content.phases[0].label == "30天"

    def test_build_html(self):
        from pipeline.layouts.narrative import NarrativeContent, PhaseItem
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("narrative")
        content = NarrativeContent(
            title="实施路线图",
            phases=[
                PhaseItem(label="阶段1", title="启动", desc="项目启动"),
                PhaseItem(label="阶段2", title="扩展", desc="规模扩展"),
            ],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "阶段1" in html
        assert "启动" in html
