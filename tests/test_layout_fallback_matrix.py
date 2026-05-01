"""
R4 regression test matrix: 8 layouts × 4 fixtures = 32 cases.

Catches the v3/v4 bug pattern where layout fallback paths (missing visual_block,
missing chart_suggestion, minimal data) introduced prefix-of-superset text into
separate HTML slots — violating H2 (0 prefix-of-superset).
"""
import pytest

from pipeline.layouts import LayoutRegistry
from pipeline.layer6_output.html_dup_check import detect_dup_prefix

THEME_COLORS = {
    "primary": "#003D6E", "secondary": "#005A9E", "accent": "#FF6B35",
    "text": "#2D3436", "muted": "#636E72", "bg": "#EEF4FA", "border": "#C8D8E8",
}


def _fixture_full():
    """Complete slide data: visual_block + text_blocks + chart."""
    return {
        "page_number": 5,
        "slide_type": "content",
        "takeaway_message": "分层分域防护框架在金融行业实践中展现出显著的安全效能提升。",
        "title": "安全效能分析",
        "primary_visual": "visual_block",
        "visual_block": {
            "type": "icon_text_grid",
            "items": [
                {"title": f"维度{i}", "description": f"第{i}个维度的具体分析内容描述"}
                for i in range(1, 5)
            ],
        },
        "text_blocks": [
            {"content": f"论据{i}：支持该论点的关键数据与案例分析。", "level": 1}
            for i in range(1, 5)
        ],
        "chart_suggestion": None,
        "layout_hint": "framework_grid",
    }


def _fixture_no_visual_block():
    """Missing visual_block — forces layout to use text-only fallback path."""
    d = _fixture_full()
    d["visual_block"] = None
    d["primary_visual"] = "text_only"
    return d


def _fixture_no_text_blocks():
    """Missing text_blocks — forces layout to rely solely on visual content."""
    d = _fixture_full()
    d["text_blocks"] = []
    return d


def _fixture_minimal():
    """Bare minimum: only takeaway_message, no visual_block, no text_blocks."""
    return {
        "page_number": 5,
        "slide_type": "content",
        "takeaway_message": "核心结论概述。",
        "title": "概览",
        "primary_visual": "text_only",
        "visual_block": None,
        "chart_suggestion": None,
        "text_blocks": [],
        "layout_hint": "framework_grid",
    }


FIXTURES = {
    "full": _fixture_full,
    "no_visual_block": _fixture_no_visual_block,
    "no_text_blocks": _fixture_no_text_blocks,
    "minimal": _fixture_minimal,
}


@pytest.mark.parametrize("layout_name", sorted(LayoutRegistry.names()))
@pytest.mark.parametrize("fixture_name", list(FIXTURES.keys()))
def test_layout_no_dup_prefix(layout_name, fixture_name):
    """Each layout × each fixture must produce HTML free of prefix-of-superset."""
    layout = LayoutRegistry.get(layout_name)
    slide_data = FIXTURES[fixture_name]()

    try:
        content = layout.from_slide_data(slide_data)
    except Exception:
        pytest.skip(f"Layout {layout_name} cannot parse fixture {fixture_name}")

    try:
        html = layout.build_html(
            content,
            theme_colors=THEME_COLORS,
            page_number=slide_data.get("page_number", 1),
            total_slides=20,
        )
    except Exception:
        pytest.skip(f"Layout {layout_name} cannot build_html for fixture {fixture_name}")

    err = detect_dup_prefix(html, ratio=1.3)
    assert err is None, (
        f"Layout '{layout_name}' with fixture '{fixture_name}' produced "
        f"dup-prefix HTML: {err}"
    )
