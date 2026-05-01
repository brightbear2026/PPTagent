"""R6 test: dense_b2b theme registration and section colors."""
from pipeline.layer4_visual.theme_registry import ThemeRegistry


def test_dense_b2b_registered():
    tr = ThemeRegistry()
    assert "dense_b2b" in tr.list_themes()


def test_dense_b2b_has_section_colors():
    tr = ThemeRegistry()
    theme = tr.get_theme("dense_b2b")
    assert theme.theme_id == "dense_b2b"
    assert theme.colors.get("section_color_1") is not None
    assert len([k for k in theme.colors if k.startswith("section_color_")]) == 6


def test_dense_b2b_smaller_font_sizes():
    tr = ThemeRegistry()
    theme = tr.get_theme("dense_b2b")
    formal = tr.get_theme("consulting_formal")
    assert theme.font_sizes["title"] < formal.font_sizes["title"]
    assert theme.font_sizes["body"] <= formal.font_sizes["body"]


def test_dense_b2b_background_not_white():
    tr = ThemeRegistry()
    theme = tr.get_theme("dense_b2b")
    assert theme.colors["background"] != "#FFFFFF"


def test_select_by_context_b2b():
    tr = ThemeRegistry()
    theme = tr.select_by_context("b2b")
    assert theme.theme_id == "dense_b2b"
    theme2 = tr.select_by_context("presales")
    assert theme2.theme_id == "dense_b2b"


def test_existing_themes_unchanged():
    tr = ThemeRegistry()
    for tid in ["consulting_formal", "tech_modern", "business_minimalist", "finance_stable", "creative_vibrant"]:
        theme = tr.get_theme(tid)
        assert theme.colors.get("section_color_1") is None, f"{tid} should not have section colors"
