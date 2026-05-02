"""R9 test: density guard catches sparse layouts and placeholder chars."""
import pytest
from pipeline.layer6_output.html_density_check import detect_sparse, detect_placeholder_char


def _make_html(elements_html: str) -> str:
    return (
        '<!DOCTYPE html><html><body style="width:960px;height:540px;">'
        f'{elements_html}'
        '</body></html>'
    )


def _p_elements(n: int, prefix: str = "Text") -> str:
    return "\n".join(f'<p style="font-size:12px;">{prefix} {i+1}</p>' for i in range(n))


class TestDetectSparse:
    def test_sparse_4_elements_triggers(self):
        html = _make_html(_p_elements(4))
        result = detect_sparse(html, min_visible=8)
        assert result is not None
        assert "4 visible" in result

    def test_dense_10_elements_passes(self):
        html = _make_html(_p_elements(10))
        assert detect_sparse(html, min_visible=8) is None

    def test_exactly_8_passes(self):
        html = _make_html(_p_elements(8))
        assert detect_sparse(html, min_visible=8) is None

    def test_empty_elements_not_counted(self):
        """Empty <p></p> should not count as visible."""
        html = _make_html('<p style="font-size:12px;"></p>' * 10)
        result = detect_sparse(html, min_visible=8)
        assert result is not None

    def test_mixed_tags_counted(self):
        """h2, li, span should all be counted."""
        html = _make_html(
            '<h2 style="font-size:16px;">Title</h2>'
            '<p style="font-size:12px;">Point 1</p>'
            '<p style="font-size:12px;">Point 2</p>'
            '<li style="font-size:12px;">Item 1</li>'
            '<li style="font-size:12px;">Item 2</li>'
            '<span style="font-size:12px;">Span 1</span>'
            '<span style="font-size:12px;">Span 2</span>'
            '<p style="font-size:12px;">Point 3</p>'
        )
        assert detect_sparse(html, min_visible=8) is None


class TestDetectPlaceholderChar:
    def test_angle_brackets_large_font_triggers(self):
        html = _make_html(
            '<h1 style="font-size:54px;color:#003D6E;"><></h1>'
        )
        result = detect_placeholder_char(html)
        assert result is not None
        assert "<>" in result

    def test_angle_brackets_small_font_passes(self):
        html = _make_html(
            '<p style="font-size:12px;"><> is a template</p>'
        )
        assert detect_placeholder_char(html) is None

    def test_dash_large_font_triggers(self):
        html = _make_html(
            '<h1 style="font-size:48px;color:#003D6E;">—</h1>'
        )
        assert detect_placeholder_char(html) is not None

    def test_normal_text_passes(self):
        html = _make_html(
            '<h2 style="font-size:16px;">正常的中文标题</h2>'
        )
        assert detect_placeholder_char(html) is None


class TestDensityGuardIntegration:
    def test_section_divider_exempt(self):
        """Section divider slides should not trigger density guard."""
        from pipeline.agents.html_design_agent import HTMLDesignAgent
        agent = HTMLDesignAgent.__new__(HTMLDesignAgent)
        sparse_html = _make_html(_p_elements(2))
        slide_data = {"slide_type": "section_divider", "page_number": 1}
        result = agent._enforce_density_guard(sparse_html, slide_data, {}, 10)
        assert result == sparse_html  # unchanged

    def test_sparse_content_triggers_fallback(self):
        """Sparse content slide should be replaced by dense fallback."""
        from pipeline.agents.html_design_agent import HTMLDesignAgent
        agent = HTMLDesignAgent.__new__(HTMLDesignAgent)
        sparse_html = _make_html(_p_elements(3))
        slide_data = {
            "slide_type": "content",
            "page_number": 1,
            "takeaway_message": "测试",
            "text_blocks": [
                {"content": "论据1"},
                {"content": "论据2"},
                {"content": "论据3"},
                {"content": "论据4"},
                {"content": "论据5"},
                {"content": "论据6"},
            ],
        }
        theme_colors = {
            "primary": "#003D6E", "secondary": "#005A9E",
            "accent": "#FF6B35", "bg": "#FFFFFF",
            "text": "#2D3436", "muted": "#636E72", "border": "#C8D8E8",
        }
        result = agent._enforce_density_guard(sparse_html, slide_data, theme_colors, 10)
        # Result should be different (dense fallback) and have more elements
        assert result != sparse_html
        # The fallback should produce ≥8 visible elements
        assert detect_sparse(result, min_visible=8) is None

    def test_dense_content_passes_through(self):
        """Dense content slide should pass through unchanged."""
        from pipeline.agents.html_design_agent import HTMLDesignAgent
        agent = HTMLDesignAgent.__new__(HTMLDesignAgent)
        dense_html = _make_html(_p_elements(12))
        slide_data = {"slide_type": "content", "page_number": 1}
        result = agent._enforce_density_guard(dense_html, slide_data, {}, 10)
        assert result == dense_html  # unchanged
