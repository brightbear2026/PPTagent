"""
R3 regression test: universal dup-prefix guard on all HTML output paths.

v4 slide 21 bug: registry layout (quote_emphasis) produced dup-prefix HTML
but the check only logged — didn't degrade. This test ensures all paths
either produce clean HTML or degrade to a safe fallback.
"""
import pytest
from unittest.mock import MagicMock, patch

from pipeline.layer6_output.html_dup_check import detect_dup_prefix


# HTML snippets that trigger dup-prefix at ratio=1.3
DUP_PREFIX_HTML = (
    '<div style="width:960px;height:540px">'
    '<p style="font-size:13pt">分层分域防护框架在关键风险点实现了60%-90%的威胁降低效果</p>'
    '<h1 style="font-size:54pt">60%</h1>'
    '<p style="font-size:12pt">分层分域防护框架在关键风险点实现</p>'
    '</div>'
)

CLEAN_HTML = (
    '<div style="width:960px;height:540px">'
    '<h2 style="font-size:18pt">主动防御四步法</h2>'
    '<p>识别、防护、监控、响应全流程覆盖</p>'
    '</div>'
)


def test_detect_dup_prefix_catches_v4_slide21_pattern():
    """The specific v4 slide 21 pattern must be caught."""
    short = "分层分域防护框架在关键风险点实现"
    long = "分层分域防护框架在关键风险点实现了60%-90%的威胁降低效果"
    html = f"<p>{long}</p><h2>{short}</h2>"
    err = detect_dup_prefix(html, ratio=1.3)
    assert err is not None


def test_clean_html_passes():
    err = detect_dup_prefix(CLEAN_HTML, ratio=1.3)
    assert err is None


def test_registry_path_degrades_on_dup_prefix():
    """Registry layout producing dup-prefix should degrade to heuristic fallback."""
    from pipeline.agents.html_design_agent import HTMLDesignAgent

    agent = HTMLDesignAgent.__new__(HTMLDesignAgent)
    agent.fallback = MagicMock()
    agent.fallback.heuristic_template_html.return_value = CLEAN_HTML
    agent.special_pages = MagicMock()
    agent.special_pages.cover_slide_html.return_value = "<html>Cover</html>"
    agent.special_pages.section_divider_html.return_value = "<html>Section</html>"
    agent.special_pages.agenda_slide_html.return_value = "<html>Agenda</html>"
    agent.llm = None
    agent._sections_list = []

    with patch("pipeline.layouts.LayoutRegistry") as MockRegistry:
        mock_layout = MagicMock()
        mock_layout.from_slide_data.return_value = MagicMock()
        mock_layout.build_html.return_value = DUP_PREFIX_HTML
        MockRegistry.names.return_value = ["quote_emphasis"]
        MockRegistry.get.return_value = mock_layout

        slide_data = {
            "slide_type": "content",
            "layout_hint": "quote_emphasis",
            "takeaway_message": "test",
        }

        result = agent._generate_slide_html(0, slide_data, {}, 5, {})

    # Should have called fallback because registry HTML had dup-prefix
    agent.fallback.heuristic_template_html.assert_called_once()


def test_heuristic_fallback_degrades_on_dup_prefix():
    """Heuristic fallback producing dup-prefix should degrade to minimal safe HTML."""
    from pipeline.agents.html_design_agent import HTMLDesignAgent

    agent = HTMLDesignAgent.__new__(HTMLDesignAgent)
    agent.fallback = MagicMock()
    agent.fallback.heuristic_template_html.return_value = DUP_PREFIX_HTML
    agent.special_pages = MagicMock()
    agent.special_pages.cover_slide_html.return_value = "<html>Cover</html>"
    agent.special_pages.section_divider_html.return_value = "<html>Section</html>"
    agent.special_pages.agenda_slide_html.return_value = "<html>Agenda</html>"
    agent.llm = None
    agent._sections_list = []

    slide_data = {
        "slide_type": "content",
        "layout_hint": "unknown_layout",
        "takeaway_message": "test takeaway",
        "text_blocks": [{"content": "论据一", "level": 1}],
    }

    result = agent._generate_slide_html(0, slide_data, {}, 5, {})

    # Should get minimal safe HTML from _minimal_safe_html, not dup-prefix HTML
    assert result != DUP_PREFIX_HTML
    assert "test takeaway" in result


def test_structural_slides_bypass_check():
    """title/section_divider/agenda slides don't go through the dup-prefix guard."""
    from pipeline.agents.html_design_agent import HTMLDesignAgent

    agent = HTMLDesignAgent.__new__(HTMLDesignAgent)
    agent.special_pages = MagicMock()
    agent.special_pages.cover_slide_html.return_value = "<html>Cover</html>"
    agent.special_pages.section_divider_html.return_value = "<html>Section</html>"
    agent.special_pages.agenda_slide_html.return_value = "<html>Agenda</html>"
    agent.llm = None
    agent._sections_list = []

    assert agent._generate_slide_html(0, {"slide_type": "title"}, {}, 5, {}) == "<html>Cover</html>"
    assert agent._generate_slide_html(0, {"slide_type": "section_divider", "title": "Ch1"}, {}, 5, {}) == "<html>Section</html>"
    assert agent._generate_slide_html(0, {"slide_type": "agenda"}, {}, 5, {}) == "<html>Agenda</html>"
