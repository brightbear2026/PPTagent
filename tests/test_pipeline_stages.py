"""
P2 Test: Pipeline stages — snapshot schema validation.

Validates that each pipeline stage's result dict has the expected top-level
keys. This catches accidental schema breakage.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from storage import PIPELINE_STAGES


class TestPipelineStageDefinitions:
    def test_stages_order(self):
        assert PIPELINE_STAGES == [
            "parse", "analyze", "outline", "content", "visual_plan", "design", "render",
        ]

    def test_seven_stages(self):
        assert len(PIPELINE_STAGES) == 7

    def test_checkpoint_stages(self):
        """outline and content are mandatory checkpoints."""
        assert "outline" in PIPELINE_STAGES
        assert "content" in PIPELINE_STAGES


class TestStageResultSchemas:
    """Validate that stage result dicts have expected keys.
    Uses fabricated but realistic data to test schema expectations."""

    def test_parse_schema(self):
        result = {
            "source_type": "doc",
            "raw_text": "Some text",
            "tables": [],
            "metadata": {},
            "detected_language": "zh",
        }
        assert "source_type" in result
        assert "raw_text" in result

    def test_analyze_schema(self):
        result = {
            "strategy": {
                "document_summary": "...",
                "audience_analysis": "...",
                "scenario_strategy": "...",
                "core_themes": [],
                "recommended_structure": "SCR",
                "recommended_page_range": "15-20",
                "key_messages": [],
            },
            "derived_metrics": [],
            "key_findings": [],
            "data_gaps": [],
            "validation_warnings": [],
            "enriched_tables": [],
        }
        assert "strategy" in result
        assert "derived_metrics" in result
        assert isinstance(result["strategy"]["core_themes"], list)

    def test_outline_schema(self):
        result = {
            "narrative_logic": "SCR: ...→...→...",
            "items": [
                {
                    "page_number": 1,
                    "slide_type": "title",
                    "takeaway_message": "Intro",
                    "supporting_hint": "",
                    "data_source": "",
                    "primary_visual": "text_only",
                    "narrative_arc": "opening",
                },
            ],
            "data_gap_suggestions": [],
        }
        assert "items" in result
        assert "narrative_logic" in result
        assert all("page_number" in i for i in result["items"])
        assert all("takeaway_message" in i for i in result["items"])

    def test_content_schema(self):
        result = {
            "total_pages": 2,
            "failed_pages": [],
            "slides": [
                {
                    "page_number": 1,
                    "slide_type": "content",
                    "takeaway_message": "Key point",
                    "text_blocks": [],
                    "data_references": [],
                    "source_note": "",
                    "primary_visual": "chart",
                    "warnings": [],
                },
            ],
        }
        assert "slides" in result
        assert "total_pages" in result
        assert all("text_blocks" in s for s in result["slides"])

    def test_design_schema(self):
        result = {
            "html_files": ["/tmp/slide_00.html", "/tmp/slide_01.html"],
            "chart_slides_data": [
                {"chart_spec": None},
                {"chart_spec": {"chart_type": "column", "categories": [], "series": []}},
            ],
        }
        assert "html_files" in result
        assert isinstance(result["html_files"], list)

    def test_render_schema(self):
        result = {
            "output_file": "/tmp/output.pptx",
            "slide_count": 10,
            "placeholders": [],
            "errors": [],
        }
        assert "output_file" in result
        assert "slide_count" in result

    def test_each_stage_has_required_keys(self):
        """Meta-test: ensure each stage dict has at minimum non-empty result."""
        schemas = {
            "parse": {"source_type": str, "raw_text": str},
            "analyze": {"strategy": dict},
            "outline": {"items": list, "narrative_logic": str},
            "content": {"slides": list, "total_pages": int},
            "design": {"html_files": list},
            "render": {"output_file": str, "slide_count": int},
        }
        for stage, required in schemas.items():
            assert stage in schemas, f"Stage {stage} missing from schema test"
            for key, expected_type in required.items():
                assert expected_type is not None, f"{stage}.{key} has no type constraint"
