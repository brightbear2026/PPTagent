"""Parametrized test: every registry layout's fallback path must not produce dup-prefix."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.layouts import LayoutRegistry
from pipeline.layer6_output.html_dup_check import detect_dup_prefix

THEME_COLORS = {"primary": "#003D6E", "accent": "#FF6B35", "bg": "#EEF4FA"}

# Slide data with NO visual_block — forces all layouts into their fallback paths.
SLIDE_WITHOUT_VBLOCK = {
    "takeaway_message": "这是一个足够长的独立标题句子",
    "text_blocks": [
        {"type": "bullet", "content": "第一条独立论据描述内容，长度适中", "level": 1},
        {"type": "bullet", "content": "第二条独立论据描述内容，长度适中", "level": 1},
        {"type": "bullet", "content": "第三条独立论据描述内容，长度适中", "level": 1},
        {"type": "bullet", "content": "第四条独立论据描述内容，长度适中", "level": 1},
    ],
}


import pytest


@pytest.mark.parametrize("layout_name", sorted(LayoutRegistry.names()))
def test_layout_fallback_no_dup_prefix(layout_name):
    layout = LayoutRegistry.get(layout_name)
    content = layout.from_slide_data(SLIDE_WITHOUT_VBLOCK)
    html = layout.build_html(content, THEME_COLORS, page_number=1, total_slides=10)
    err = detect_dup_prefix(html)
    assert err is None, f"Layout '{layout_name}' fallback produced dup-prefix: {err}"
