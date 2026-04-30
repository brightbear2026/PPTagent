"""Tests for registry-typed parallel_points, metrics, chart_focus layouts."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestRegistryAllLayouts:
    def test_all_five_registered(self):
        from pipeline.layouts import LayoutRegistry
        expected = {"call_to_action", "quote_emphasis", "parallel_points", "metrics", "chart_focus"}
        assert LayoutRegistry.names() == expected


class TestParallelPointsLayout:
    def test_from_slide_data(self):
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("parallel_points")
        sd = {
            "takeaway_message": "这是一个足够长的测试标题句子",
            "text_blocks": [
                {"type": "bullet", "content": "第一条独立论据描述内容", "level": 1},
                {"type": "bullet", "content": "第二条独立论据描述内容", "level": 1},
                {"type": "bullet", "content": "第三条独立论据描述内容", "level": 1},
            ],
        }
        content = layout.from_slide_data(sd)
        assert len(content.bullets) == 3
        assert "第一条" in content.bullets[0]

    def test_build_html(self):
        from pipeline.layouts.parallel_points import ParallelPointsContent
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("parallel_points")
        content = ParallelPointsContent(
            title="测试标题内容",
            bullets=["论据一", "论据二", "论据三"],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "论据一" in html
        assert "论据三" in html

    def test_no_dup_prefix(self):
        from pipeline.layer6_output.html_dup_check import detect_dup_prefix
        from pipeline.layouts.parallel_points import ParallelPointsContent
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("parallel_points")
        content = ParallelPointsContent(
            title="标题与正文完全不同的内容",
            bullets=["第一条论据独立完整", "第二条论据也独立完整"],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert detect_dup_prefix(html) is None


class TestMetricsLayout:
    def test_from_slide_data_with_vblock(self):
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("metrics")
        sd = {
            "takeaway_message": "关键指标显著增长趋势明显",
            "text_blocks": [{"type": "bullet", "content": "解读数据", "level": 1}],
            "visual_block": {
                "type": "kpi_cards",
                "items": [
                    {"title": "营收", "value": "32%", "description": "同比增长"},
                    {"title": "用户", "value": "1.2M", "description": "月活"},
                ],
            },
        }
        content = layout.from_slide_data(sd)
        assert len(content.metrics) == 2
        assert content.metrics[0].value == "32%"

    def test_build_html(self):
        from pipeline.layouts.metrics import MetricsContent, MetricItem
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("metrics")
        content = MetricsContent(
            title="核心指标概览",
            metrics=[
                MetricItem(label="营收", value="32%", note="同比增长"),
                MetricItem(label="用户", value="1.2M", note="月活"),
            ],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "32%" in html
        assert "1.2M" in html


class TestChartFocusLayout:
    def test_from_slide_data(self):
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("chart_focus")
        sd = {
            "takeaway_message": "图表展示关键趋势变化",
            "text_blocks": [
                {"type": "bullet", "content": "Q1趋势向上明显", "level": 1},
                {"type": "bullet", "content": "Q2增长加速", "level": 1},
            ],
        }
        content = layout.from_slide_data(sd)
        assert len(content.annotations) == 2

    def test_build_html_has_chart_placeholder(self):
        from pipeline.layouts.chart_focus import ChartFocusContent
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("chart_focus")
        content = ChartFocusContent(
            title="趋势图表",
            annotations=["注解一", "注解二"],
        )
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert "chart-0" in html
        assert "placeholder" in html
        assert "注解一" in html
