"""Tests for R32 — Image rendering in image_text_grid."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGridImageItemImagePath:
    def test_item_has_image_path(self):
        from pipeline.layouts.image_text_grid import GridImageItem
        item = GridImageItem(title="Test", image_path="/tmp/img.png")
        assert item.image_path == "/tmp/img.png"

    def test_item_default_no_image_path(self):
        from pipeline.layouts.image_text_grid import GridImageItem
        item = GridImageItem(title="Test")
        assert item.image_path == ""


class TestBuildHtmlWithRealImage:
    def test_real_image_renders_img_tag(self, tmp_path):
        from pipeline.layouts.image_text_grid import ImageTextGridLayout, ImageTextGridContent, GridImageItem

        # Create a small test image
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)

        layout = ImageTextGridLayout()
        content = ImageTextGridContent(
            title="Test Title",
            items=[
                GridImageItem(title="Card1", description="Desc1", image_path=str(img_path)),
                GridImageItem(title="Card2", description="Desc2"),
                GridImageItem(title="Card3", description="Desc3"),
            ],
        )
        html = layout.build_html(content, {}, page_number=1, total_slides=1)

        # Card with real image should have <img> tag
        assert '<img src=' in html
        assert str(img_path) in html
        # Cards without image should have placeholder text
        assert "示意图" in html

    def test_nonexistent_image_falls_back_to_placeholder(self, tmp_path):
        from pipeline.layouts.image_text_grid import ImageTextGridLayout, ImageTextGridContent, GridImageItem

        layout = ImageTextGridLayout()
        content = ImageTextGridContent(
            title="Test",
            items=[
                GridImageItem(title="Card1", image_path="/nonexistent/path.png", image_caption="Custom caption"),
                GridImageItem(title="Card2"),
                GridImageItem(title="Card3"),
            ],
        )
        html = layout.build_html(content, {}, page_number=1, total_slides=1)

        # Nonexistent image → falls back to placeholder with custom caption
        assert "Custom caption" in html
        assert '<img src=' not in html


class TestFromSlideDataWithImagePath:
    def test_vblock_carries_image_path(self):
        from pipeline.layouts.image_text_grid import ImageTextGridLayout

        slide_data = {
            "takeaway_message": "Test",
            "visual_block": {
                "type": "image_text_grid",
                "items": [
                    {"title": "Card1", "description": "Desc1", "image_path": "/tmp/a.png"},
                    {"title": "Card2", "description": "Desc2", "image_path": "/tmp/b.png"},
                    {"title": "Card3", "description": "Desc3"},
                ],
            },
        }
        layout = ImageTextGridLayout()
        content = layout.from_slide_data(slide_data)

        assert content.items[0].image_path == "/tmp/a.png"
        assert content.items[1].image_path == "/tmp/b.png"
        assert content.items[2].image_path == ""
