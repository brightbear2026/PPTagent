"""R7 test: hero_splash template fully removed, hero pages demoted to dense layouts."""
from pipeline.agents.design_strategies.templates import TemplatePicker
from pipeline.layer6_output.slide_templates import TEMPLATES, TEMPLATE_SCHEMAS


def test_hero_splash_not_in_templates():
    assert "hero_splash" not in TEMPLATES, "hero_splash HTML template must be removed"


def test_hero_splash_not_in_schemas():
    assert "hero_splash" not in TEMPLATE_SCHEMAS, "hero_splash schema must be removed"


def test_hero_splash_not_in_layout_hint_map():
    values = set(TemplatePicker.LAYOUT_HINT_MAP.values())
    assert "hero_splash" not in values, "hero_splash must not appear in LAYOUT_HINT_MAP values"


def test_hero_page_demoted_icon_grid():
    """hero page_weight with <4 body blocks → icon_grid (not hero_splash)."""
    slide_data = {
        "page_weight": "hero",
        "takeaway_message": "核心增长",
        "visual_block": {"type": "icon_text_grid", "items": [
            {"title": "增长1", "description": "desc1"},
            {"title": "增长2", "description": "desc2"},
        ]},
    }
    body_blocks = [{"content": "支撑1"}, {"content": "支撑2"}]
    template_id, slots = TemplatePicker.pick(slide_data, body_blocks, [], "核心增长")
    assert template_id != "hero_splash", f"hero page must not use hero_splash, got {template_id}"
    assert template_id in ("icon_grid", "content_key_metrics", "content_bullets"), \
        f"Expected dense layout, got {template_id}"


def test_hero_page_demoted_metrics_many_blocks():
    """hero page_weight with ≥4 body blocks → content_key_metrics."""
    slide_data = {"page_weight": "hero", "takeaway_message": "数据分析"}
    body_blocks = [
        {"content": "营收增长32%"},
        {"content": "用户数达1.2亿"},
        {"content": "市场份额提升5个百分点"},
        {"content": "客户满意度95%"},
    ]
    template_id, slots = TemplatePicker.pick(slide_data, body_blocks, [], "数据分析")
    assert template_id == "content_key_metrics", f"Expected content_key_metrics, got {template_id}"


def test_no_hero_splash_grep():
    """Grep check: zero hero_splash references in Python source."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.md",
         "hero_splash", "pipeline/"],
        capture_output=True, text=True,
    )
    # Only allowed: the one comment line in templates.py
    matches = [l for l in result.stdout.strip().split("\n") if l]
    comment_lines = [l for l in matches if "# " in l and "deleted" in l]
    code_lines = [l for l in matches if l not in comment_lines]
    assert len(code_lines) == 0, f"Found hero_splash in code:\n" + "\n".join(code_lines)
