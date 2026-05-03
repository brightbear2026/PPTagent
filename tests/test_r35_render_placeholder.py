"""Tests for R35 — Render failed page placeholder."""
import pytest
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestRenderPlaceholderLogic:
    """Verify placeholder logic is in the JS render files."""

    def test_wrapper_has_placeholder_fallback(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "pipeline", "layer6_output", "html2pptx_wrapper.js")) as f:
            content = f.read()
        assert "recovered_with_placeholder" in content
        assert "_placeholder_" in content
        assert "该页生成失败" in content

    def test_server_has_placeholder_fallback(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "pipeline", "layer6_output", "render_server.js")) as f:
            content = f.read()
        assert "recovered_with_placeholder" in content
        assert "_placeholder_" in content
        assert "该页生成失败" in content

    def test_wrapper_catch_writes_placeholder_html(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "pipeline", "layer6_output", "html2pptx_wrapper.js")) as f:
            content = f.read()
        # Verify the catch block writes placeholder and renders it
        assert "writeFileSync" in content
        assert "html2pptx(phPath" in content or "html2pptx(phPath" in content
        # Verify cleanup
        assert "unlinkSync(phPath)" in content

    def test_wrapper_has_last_resort_empty_slide(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "pipeline", "layer6_output", "html2pptx_wrapper.js")) as f:
            content = f.read()
        # Last resort: add empty slide if even placeholder rendering fails
        assert "pptx.addSlide()" in content
        assert "render failed" in content

    def test_placeholder_html_structure(self):
        """Verify the placeholder HTML has correct dimensions and content."""
        with open(os.path.join(os.path.dirname(__file__), "..", "pipeline", "layer6_output", "html2pptx_wrapper.js")) as f:
            content = f.read()
        assert "1280px" in content  # canvas width
        assert "720px" in content  # canvas height
        assert "#f5f5f5" in content  # light gray background
        assert "Page ${i + 1}" in content or "Page ${i+1}" in content
