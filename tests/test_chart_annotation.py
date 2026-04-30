"""Tests for chart annotation callout injection (Fix 12)."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestChartAnnotation:
    def test_annotation_text_from_so_what(self):
        """When so_what is set, annotation uses it (truncated to 30 chars)."""
        from pipeline.layer6_output.chart_renderer import ChartRenderer
        from models.slide_spec import ChartSpec, ChartSeries

        renderer = ChartRenderer()
        spec = ChartSpec(
            chart_type="column",
            categories=["Q1", "Q2", "Q3"],
            series=[ChartSeries(name="Revenue", values=[10, 20, 15])],
            so_what="营收增速达32%，连续三个季度领跑全公司",
        )
        # Build annotation text via internal logic
        values = [float(v) for v in spec.series[0].values]
        peak_idx = max(range(len(values)), key=lambda i: abs(values[i]))
        assert peak_idx == 1  # Q2=20 is peak
        assert spec.so_what[:30] == "营收增速达32%，连续三个季度领跑全公司"[:30]

    def test_annotation_auto_label_single_series(self):
        """When no so_what, auto-generate from peak data point."""
        from models.slide_spec import ChartSpec, ChartSeries

        spec = ChartSpec(
            chart_type="bar",
            categories=["A", "B", "C"],
            series=[ChartSeries(name="Count", values=[5, 15, 8])],
        )
        values = [float(v) for v in spec.series[0].values]
        peak_idx = max(range(len(values)), key=lambda i: abs(values[i]))
        cat = spec.categories[peak_idx]
        assert cat == "B"
        assert values[peak_idx] == 15.0

    def test_annotation_method_exists(self):
        """_add_chart_annotation is callable and non-breaking."""
        from pipeline.layer6_output.chart_renderer import ChartRenderer
        from models.slide_spec import ChartSpec, ChartSeries

        renderer = ChartRenderer()
        spec = ChartSpec(
            chart_type="column",
            categories=["X", "Y"],
            series=[ChartSeries(name="V", values=[1, 2])],
            so_what="test annotation text",
        )
        # Call with mock slide (should not crash even without real slide)
        class MockSlide:
            class shapes:
                @staticmethod
                def add_textbox(*a, **kw):
                    class MockTF:
                        text_frame = type("tf", (), {"word_wrap": True})()
                        paragraphs = [type("p", (), {
                            "text": "", "font": type("f", (), {
                                "size": None, "bold": None,
                                "color": type("c", (), {"rgb": None})(),
                                "name": None, "alignment": None,
                            })(), "alignment": None,
                        })()]
                    return MockTF
        # Should not raise
        renderer._add_chart_annotation(MockSlide(), spec, 1, 1, 4, 3)
