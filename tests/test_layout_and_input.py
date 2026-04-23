"""
单元测试：布局引擎和模板库
"""
import unittest

from models import SlideSpec, ContentPattern, LayoutCoordinates, Rect


class TestLayoutSkeletonRegistry(unittest.TestCase):
    def test_load_all_skeletons(self):
        from templates.skeleton_registry import LayoutSkeletonRegistry
        registry = LayoutSkeletonRegistry()
        all_s = registry.list_skeletons()
        self.assertEqual(len(all_s), 22)

    def test_core_skeletons(self):
        from templates.skeleton_registry import LayoutSkeletonRegistry
        registry = LayoutSkeletonRegistry()
        core = registry.list_skeletons(category="core")
        self.assertEqual(len(core), 12)

    def test_extended_skeletons(self):
        from templates.skeleton_registry import LayoutSkeletonRegistry
        registry = LayoutSkeletonRegistry()
        ext = registry.list_skeletons(category="extended")
        self.assertEqual(len(ext), 6)

    def test_get_skeleton(self):
        from templates.skeleton_registry import LayoutSkeletonRegistry
        registry = LayoutSkeletonRegistry()
        s = registry.get("title_center")
        self.assertIsNotNone(s)
        self.assertEqual(s.name, "标题居中")
        self.assertIn("title", s.slots)

    def test_get_nonexistent_returns_none(self):
        from templates.skeleton_registry import LayoutSkeletonRegistry
        registry = LayoutSkeletonRegistry()
        self.assertIsNone(registry.get("nonexistent"))

    def test_resolve_rects(self):
        from templates.skeleton_registry import LayoutSkeletonRegistry
        registry = LayoutSkeletonRegistry()
        rects = registry.resolve_slots_to_rects("split_50_50")
        self.assertIsNotNone(rects)
        self.assertIn("left", rects)
        self.assertIn("right", rects)
        # Left and right should not overlap
        left = rects["left"]
        right = rects["right"]
        self.assertLess(left.left + left.width, right.left)

    def test_all_skeletons_resolve(self):
        from templates.skeleton_registry import LayoutSkeletonRegistry
        registry = LayoutSkeletonRegistry()
        for s in registry.list_skeletons():
            rects = registry.resolve_slots_to_rects(s.skeleton_id)
            self.assertIsNotNone(rects, f"Failed to resolve {s.skeleton_id}")
            self.assertGreater(len(rects), 0, f"Empty rects for {s.skeleton_id}")


class TestLayoutEngine(unittest.TestCase):
    def test_template_based_layout(self):
        from pipeline.layer6_output.layout_engine import LayoutEngine
        engine = LayoutEngine()

        slide = SlideSpec(slide_id="test", slide_type="content")
        slide.content_pattern = ContentPattern.TWO_COLUMN
        slide.layout_template_id = "split_50_50"

        coords = engine.calculate_layout(slide)
        self.assertIsNotNone(coords.title_area)
        self.assertEqual(len(coords.body_areas), 2)

    def test_fallback_hardcoded(self):
        from pipeline.layer6_output.layout_engine import LayoutEngine
        engine = LayoutEngine()

        slide = SlideSpec(slide_id="test", slide_type="content")
        slide.content_pattern = ContentPattern.ARGUMENT_EVIDENCE

        coords = engine.calculate_layout(slide)
        self.assertIsNotNone(coords.title_area)

    def test_title_page(self):
        from pipeline.layer6_output.layout_engine import LayoutEngine
        engine = LayoutEngine()

        slide = SlideSpec(slide_id="test", slide_type="title")
        slide.content_pattern = ContentPattern.TITLE_ONLY
        slide.layout_template_id = "title_center"

        coords = engine.calculate_layout(slide)
        self.assertIsNotNone(coords.title_area)

    def test_matrix_layout(self):
        from pipeline.layer6_output.layout_engine import LayoutEngine
        engine = LayoutEngine()

        slide = SlideSpec(slide_id="test", slide_type="content")
        slide.content_pattern = ContentPattern.MATRIX_2X2
        slide.layout_template_id = "four_quadrant"

        coords = engine.calculate_layout(slide)
        self.assertEqual(len(coords.body_areas), 4)

    def test_invalid_template_falls_back(self):
        from pipeline.layer6_output.layout_engine import LayoutEngine
        engine = LayoutEngine()

        slide = SlideSpec(slide_id="test", slide_type="content")
        slide.content_pattern = ContentPattern.THREE_COLUMN
        slide.layout_template_id = "nonexistent"

        coords = engine.calculate_layout(slide)
        # Falls back to hardcoded _layout_three_column
        self.assertIsNotNone(coords.title_area)
        self.assertEqual(len(coords.body_areas), 3)


class TestInputRouter(unittest.TestCase):
    def test_markdown_parsing(self):
        import tempfile, os
        from pipeline.layer1_input import InputRouter

        # Create temp markdown file
        content = "# Test\n\nHello world\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            path = f.name

        try:
            router = InputRouter()
            result = router.parse(file_path=path)
            self.assertEqual(result.source_type, "markdown")
            self.assertEqual(len(result.tables), 1)
            self.assertEqual(result.tables[0].headers, ["A", "B"])
        finally:
            os.unlink(path)

    def test_text_parsing(self):
        from pipeline.layer1_input import InputRouter
        router = InputRouter()
        result = router.parse(text="Hello world")
        self.assertEqual(result.source_type, "text")

    def test_unsupported_format(self):
        from pipeline.layer1_input import InputRouter
        router = InputRouter()
        with self.assertRaises(ValueError):
            router.parse(file_path="test.xyz")


if __name__ == "__main__":
    unittest.main()
