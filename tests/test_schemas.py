"""
Tests for pipeline stage pydantic schemas and schema_adapter.

Covers:
- ContentSlideSchema: infer primary_visual, visual content present, mutual exclusion
- degrade_to_text_only: preserve text_blocks, clear visuals
- make_placeholder: is_failed stub
- ParseResult tagged: json_parse vs schema errors
- OutlineItemSchema: normalize primary_visual, narrative_arc
- ContentResultSchema: computed fields
- Round-trip: model_validate → model_dump(mode="json") consistency
- Enum usage: SlideType / NarrativeRole serialize correctly
"""

import pytest
from pydantic import ValidationError

from models.schemas import (
    ContentResultSchema,
    ContentSlideSchema,
    OutlineItemSchema,
    OutlineResultSchema,
    ParseResult,
)
from models.schema_adapter import (
    content_schema_to_dict,
    degrade_to_text_only,
    make_placeholder,
    parse_slide,
    validate_outline,
)
from models.slide_spec import NarrativeRole, PrimaryVisualType, SlideType


def _min_text_blocks():
    """Minimal text_blocks satisfying min_length=4 and density>=300 for content slides."""
    return [
        {"type": "heading", "text": "综合分析报告：技术架构优化与市场表现的全面评估总结与深度分析"},
        {"type": "bullet", "text": "微服务架构改造完成后系统整体响应性能实现显著提升，核心接口平均响应时间从原先的八百毫秒大幅缩减至两百毫秒以内，P99尾延迟指标改善幅度达到百分之七十五以上，建议在下一阶段将此优化方案推广至全业务线", "level": 1},
        {"type": "bullet", "text": "华东区域市场份额连续三个季度保持稳步增长态势，从百分之十八提升至百分之二十四，成功超越主要竞争对手成为该区域市场排名第二的参与者，该增长趋势与渠道下沉策略和本地化运营投入密切相关联", "level": 1},
        {"type": "bullet", "text": "平台用户留存率和付费转化率双双创下历史最高纪录，月活跃用户规模突破一百二十万大关，充分验证了产品核心功能迭代升级与精细化用户运营双轮驱动策略的有效性与长期可持续发展潜力", "level": 1},
    ]


# ---------------------------------------------------------------------------
# ContentSlideSchema — infer primary_visual
# ---------------------------------------------------------------------------


class TestInferPrimaryVisual:
    def test_explicit_text_only_with_chart_rejected(self):
        """Explicit text_only + chart_suggestion should be caught by mutual exclusion."""
        with pytest.raises(ValidationError, match="text_only.*visual"):
            ContentSlideSchema(
                page_number=1,
                primary_visual="text_only",
                chart_suggestion={"chart_type": "bar", "series": [{"values": [1, 2]}]},
            )

    def test_empty_pv_infers_from_chart(self):
        s = ContentSlideSchema(
            page_number=1,
            primary_visual="",
            chart_suggestion={"chart_type": "bar", "series": [{"values": [1, 2]}]},
            text_blocks=_min_text_blocks(),
        )
        assert s.primary_visual == PrimaryVisualType.CHART

    def test_text_pv_infers_from_diagram(self):
        s = ContentSlideSchema(
            page_number=1,
            primary_visual="text",
            diagram_spec={"diagram_type": "process_flow"},
            text_blocks=_min_text_blocks(),
        )
        assert s.primary_visual == PrimaryVisualType.DIAGRAM

    def test_no_visual_infers_text_only(self):
        s = ContentSlideSchema(page_number=1, text_blocks=_min_text_blocks())
        assert s.primary_visual == PrimaryVisualType.TEXT_ONLY

    def test_explicit_pv_not_overridden(self):
        s = ContentSlideSchema(
            page_number=1,
            primary_visual="chart",
            chart_suggestion={"chart_type": "bar", "series": [{"values": [1, 2]}]},
            text_blocks=_min_text_blocks(),
        )
        assert s.primary_visual == PrimaryVisualType.CHART


# ---------------------------------------------------------------------------
# ContentSlideSchema — visual content present
# ---------------------------------------------------------------------------


class TestVisualContentPresent:
    def test_chart_with_series_passes(self):
        ContentSlideSchema(
            page_number=1,
            primary_visual="chart",
            chart_suggestion={"chart_type": "bar", "series": [{"values": [10, 20]}]},
            text_blocks=_min_text_blocks(),
        )

    def test_chart_with_labels_passes(self):
        ContentSlideSchema(
            page_number=1,
            primary_visual="chart",
            chart_suggestion={"chart_type": "pie", "categories": ["A", "B"]},
            text_blocks=_min_text_blocks(),
        )

    def test_chart_no_data_rejected(self):
        with pytest.raises(ValidationError, match="no data"):
            ContentSlideSchema(
                page_number=1,
                primary_visual="chart",
                chart_suggestion={"chart_type": "bar"},
            )

    def test_chart_empty_series_rejected(self):
        with pytest.raises(ValidationError, match="no data"):
            ContentSlideSchema(
                page_number=1,
                primary_visual="chart",
                chart_suggestion={"chart_type": "bar", "series": []},
            )

    def test_diagram_no_type_rejected(self):
        with pytest.raises(ValidationError, match="no diagram_type"):
            ContentSlideSchema(
                page_number=1,
                primary_visual="diagram",
                diagram_spec={},
            )

    def test_diagram_with_type_passes(self):
        ContentSlideSchema(
            page_number=1,
            primary_visual="diagram",
            diagram_spec={"diagram_type": "process_flow"},
            text_blocks=_min_text_blocks(),
        )

    def test_vblock_no_type_rejected(self):
        with pytest.raises(ValidationError, match="no type"):
            ContentSlideSchema(
                page_number=1,
                primary_visual="visual_block",
                visual_block={"items": [{"title": "A"}]},
            )

    def test_vblock_empty_items_rejected(self):
        with pytest.raises(ValidationError, match="items is empty"):
            ContentSlideSchema(
                page_number=1,
                primary_visual="visual_block",
                visual_block={"type": "kpi_cards", "items": []},
            )

    def test_vblock_valid_passes(self):
        ContentSlideSchema(
            page_number=1,
            primary_visual="visual_block",
            visual_block={"type": "kpi_cards", "items": [{"title": "Revenue", "value": "$1B"}]},
            text_blocks=_min_text_blocks(),
        )


# ---------------------------------------------------------------------------
# ContentSlideSchema — mutual exclusion
# ---------------------------------------------------------------------------


class TestMutualExclusion:
    def test_text_only_with_no_visuals_passes(self):
        ContentSlideSchema(page_number=1, primary_visual="text_only", text_blocks=_min_text_blocks())

    def test_chart_with_diagram_rejected(self):
        with pytest.raises(ValidationError, match="chart.*diagram"):
            ContentSlideSchema(
                page_number=1,
                primary_visual="chart",
                chart_suggestion={"chart_type": "bar", "series": [{"values": [1]}]},
                diagram_spec={"diagram_type": "process_flow"},
            )

    def test_chart_with_vblock_rejected(self):
        with pytest.raises(ValidationError, match="chart.*vblock"):
            ContentSlideSchema(
                page_number=1,
                primary_visual="chart",
                chart_suggestion={"chart_type": "bar", "series": [{"values": [1]}]},
                visual_block={"type": "kpi_cards", "items": [{"title": "X"}]},
            )

    def test_text_only_with_chart_rejected(self):
        with pytest.raises(ValidationError, match="text_only.*visual"):
            ContentSlideSchema(
                page_number=1,
                primary_visual="text_only",
                chart_suggestion={"chart_type": "bar"},
            )

    def test_chart_only_passes(self):
        ContentSlideSchema(
            page_number=1,
            primary_visual="chart",
            chart_suggestion={"chart_type": "bar", "series": [{"values": [1]}]},
            text_blocks=_min_text_blocks(),
        )


# ---------------------------------------------------------------------------
# degrade_to_text_only
# ---------------------------------------------------------------------------


class TestDegradeToTextOnly:
    def test_preserves_text_blocks(self):
        raw = {
            "page_number": 1,
            "takeaway_message": "Revenue grew 20%",
            "text_blocks": [{"type": "bullet", "text": "Revenue hit $1B"}],
            "chart_suggestion": {"chart_type": "bar", "series": [{"values": [1]}]},
            "diagram_spec": {"diagram_type": "flow"},
        }
        result = degrade_to_text_only(raw)
        assert result.primary_visual == PrimaryVisualType.TEXT_ONLY
        assert result.chart_suggestion is None
        assert result.diagram_spec is None
        assert result.visual_block is None
        # Padded to min_length=4 in fallback path
        assert len(result.text_blocks) == 4
        assert result.text_blocks[0]["text"] == "Revenue hit $1B"

    def test_error_message_cleared(self):
        raw = {"page_number": 2, "error_message": "some error"}
        result = degrade_to_text_only(raw)
        assert result.error_message == "degraded_from_schema_violation"


# ---------------------------------------------------------------------------
# make_placeholder
# ---------------------------------------------------------------------------


class TestMakePlaceholder:
    def test_is_failed_true(self):
        p = make_placeholder(page_number=3, title="Test", takeaway="Summary")
        assert p.is_failed is True
        assert p.error_message == "content_generation_failed"
        assert p.primary_visual == PrimaryVisualType.TEXT_ONLY
        assert len(p.text_blocks) == 4

    def test_minimal(self):
        p = make_placeholder(page_number=5)
        assert p.page_number == 5
        assert p.is_failed is True


# ---------------------------------------------------------------------------
# ParseResult tagged
# ---------------------------------------------------------------------------


class TestParseResult:
    def test_ok_result(self):
        pr = ParseResult(
            schema=ContentSlideSchema(page_number=1, text_blocks=_min_text_blocks()),
            error_kind="ok",
        )
        assert pr.error_kind == "ok"
        assert pr.schema is not None

    def test_json_parse_error(self):
        pr = ParseResult(error_kind="json_parse", error_msg="no JSON found")
        assert pr.error_kind == "json_parse"
        assert pr.schema is None
        assert pr.raw_data is None

    def test_schema_error_with_raw_data(self):
        pr = ParseResult(
            error_kind="schema",
            error_msg="mutual exclusion violated",
            raw_data={"page_number": 1, "text_blocks": []},
        )
        assert pr.error_kind == "schema"
        assert pr.raw_data is not None


# ---------------------------------------------------------------------------
# parse_slide
# ---------------------------------------------------------------------------


class TestParseSlide:
    def test_valid_json(self):
        import json as _json
        data = {"text_blocks": _min_text_blocks(), "page_number": 1}
        json_text = f'```json\n{_json.dumps(data, ensure_ascii=False)}\n```'
        pr = parse_slide(json_text, 1)
        assert pr.error_kind == "ok"
        assert pr.schema.page_number == 1

    def test_no_json(self):
        pr = parse_slide("This is just plain text", 1)
        assert pr.error_kind == "json_parse"

    def test_schema_violation(self):
        # chart + diagram simultaneously → schema rejection
        bad_json = '{"page_number": 1, "text_blocks": [{"text": "x"}], "chart_suggestion": {"series": [{"values": [1]}]}, "diagram_spec": {"diagram_type": "flow"}}'
        pr = parse_slide(bad_json, 1)
        assert pr.error_kind == "schema"
        assert pr.raw_data is not None


# ---------------------------------------------------------------------------
# OutlineItemSchema
# ---------------------------------------------------------------------------


class TestOutlineItemSchema:
    def test_empty_pv_normalized(self):
        item = OutlineItemSchema(page_number=1, primary_visual="")
        assert item.primary_visual == PrimaryVisualType.TEXT_ONLY

    def test_text_pv_normalized(self):
        item = OutlineItemSchema(page_number=1, primary_visual="text")
        assert item.primary_visual == PrimaryVisualType.TEXT_ONLY

    def test_invalid_narrative_arc_normalized(self):
        item = OutlineItemSchema(page_number=1, narrative_arc="weird_value")
        assert item.narrative_arc == NarrativeRole.EVIDENCE

    def test_valid_narrative_arc_passes(self):
        item = OutlineItemSchema(page_number=1, narrative_arc="opening")
        assert item.narrative_arc == NarrativeRole.OPENING

    def test_page_number_must_be_positive(self):
        with pytest.raises(ValidationError):
            OutlineItemSchema(page_number=0)


# ---------------------------------------------------------------------------
# ContentResultSchema — computed fields
# ---------------------------------------------------------------------------


class TestContentResultSchema:
    def test_total_pages(self):
        r = ContentResultSchema(slides=[
            ContentSlideSchema(page_number=1, text_blocks=_min_text_blocks()),
            ContentSlideSchema(page_number=2, text_blocks=_min_text_blocks()),
        ])
        assert r.total_pages == 2

    def test_failed_pages(self):
        r = ContentResultSchema(slides=[
            ContentSlideSchema(page_number=1, is_failed=True, text_blocks=_min_text_blocks()),
            ContentSlideSchema(page_number=2, text_blocks=_min_text_blocks()),
            ContentSlideSchema(page_number=3, is_failed=True, text_blocks=_min_text_blocks()),
        ])
        assert r.failed_pages == [1, 3]

    def test_empty_result(self):
        r = ContentResultSchema()
        assert r.total_pages == 0
        assert r.failed_pages == []


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_content_slide_round_trip(self):
        data = {
            "page_number": 1,
            "slide_type": "content",
            "takeaway_message": "Revenue grew 20%",
            "text_blocks": _min_text_blocks(),
            "primary_visual": "text_only",
        }
        schema = ContentSlideSchema.model_validate(data)
        dumped = schema.model_dump(mode="json")
        assert dumped["page_number"] == 1
        assert dumped["primary_visual"] == "text_only"
        assert dumped["slide_type"] == "content"
        assert len(dumped["text_blocks"]) == 4

    def test_content_result_round_trip_via_adapter(self):
        slides = [
            ContentSlideSchema(
                page_number=1,
                primary_visual="chart",
                chart_suggestion={"chart_type": "bar", "series": [{"values": [10, 20]}]},
                text_blocks=_min_text_blocks(),
            ),
            ContentSlideSchema(page_number=2, text_blocks=_min_text_blocks()),
        ]
        result = ContentResultSchema(slides=slides)
        dumped = content_schema_to_dict(result)
        assert dumped["total_pages"] == 2
        assert dumped["slides"][0]["primary_visual"] == "chart"
        assert dumped["failed_pages"] == []


# ---------------------------------------------------------------------------
# Enum usage
# ---------------------------------------------------------------------------


class TestEnumSerialization:
    def test_slide_type_enum_in_json(self):
        s = ContentSlideSchema(page_number=1, slide_type="title", text_blocks=_min_text_blocks())
        dumped = s.model_dump(mode="json")
        assert dumped["slide_type"] == "title"
        assert isinstance(dumped["slide_type"], str)

    def test_narrative_role_enum_in_json(self):
        item = OutlineItemSchema(page_number=1, narrative_arc="closing")
        dumped = item.model_dump(mode="json")
        assert dumped["narrative_arc"] == "closing"
        assert isinstance(dumped["narrative_arc"], str)

    def test_primary_visual_enum_in_json(self):
        s = ContentSlideSchema(
            page_number=1,
            primary_visual="chart",
            chart_suggestion={"chart_type": "bar", "series": [{"values": [1]}]},
            text_blocks=_min_text_blocks(),
        )
        dumped = s.model_dump(mode="json")
        assert dumped["primary_visual"] == "chart"


# ---------------------------------------------------------------------------
# validate_outline
# ---------------------------------------------------------------------------


class TestValidateOutline:
    def test_valid_outline_no_errors(self):
        data = {"items": [{"page_number": 1, "slide_type": "title"}]}
        errors = validate_outline(data)
        assert errors == []

    def test_invalid_page_number(self):
        data = {"items": [{"page_number": 0}]}
        errors = validate_outline(data)
        assert len(errors) > 0

    def test_accepts_slides_key(self):
        data = {"slides": [{"page_number": 1}]}
        errors = validate_outline(data)
        assert errors == []


# ---------------------------------------------------------------------------
# page_weight enum — must accept all 4 values used in the pipeline
# ---------------------------------------------------------------------------


class TestPageWeightEnum:
    """page_weight Literal must include every value the pipeline actually uses.
    Regression: 'transition' was missing — PlanAgent injects it for
    title/agenda/section_divider, css_linter uses it for density thresholds."""

    @pytest.mark.parametrize("pw", ["hero", "pillar", "supporting", "transition"])
    def test_outline_item_accepts_all_weights(self, pw):
        item = OutlineItemSchema(page_number=1, page_weight=pw)
        assert item.page_weight == pw

    @pytest.mark.parametrize("pw", ["hero", "pillar", "supporting", "transition"])
    def test_content_slide_accepts_all_weights(self, pw):
        slide = ContentSlideSchema(page_number=1, page_weight=pw, text_blocks=_min_text_blocks())
        assert slide.page_weight == pw

    def test_invalid_page_weight_rejected(self):
        with pytest.raises(ValidationError):
            OutlineItemSchema(page_number=1, page_weight="bogus")

    def test_real_world_outline_no_violations(self):
        """The exact regressed outline_dump shape should produce zero
        page_weight schema warnings after the fix."""
        items = [
            {"page_number": 1, "slide_type": "title", "page_weight": "transition"},
            {"page_number": 2, "slide_type": "agenda", "page_weight": "transition"},
            {"page_number": 3, "slide_type": "section_divider", "page_weight": "transition"},
            {"page_number": 4, "slide_type": "content", "page_weight": "hero"},
            {"page_number": 5, "slide_type": "content", "page_weight": "pillar"},
        ]
        errors = validate_outline({"items": items})
        # Filter to only page_weight-related errors
        pw_errors = [e for e in errors if "hero" in e or "pillar" in e or "supporting" in e or "transition" in e]
        assert pw_errors == [], f"Expected no page_weight errors, got: {pw_errors}"


class TestBulletLengthCap:
    def test_overlong_bullet_rejected(self):
        import pytest as _pytest
        with _pytest.raises(ValidationError):
            ContentSlideSchema(
                page_number=1,
                text_blocks=[
                    {"type": "heading", "content": "标题"},
                    {"type": "bullet", "content": "X" * 121, "level": 1},
                    {"type": "bullet", "content": "Y" * 50, "level": 1},
                    {"type": "bullet", "content": "Z" * 50, "level": 1},
                ],
            )

    def test_bullet_at_limit_accepted(self):
        slide = ContentSlideSchema(
            page_number=1,
            text_blocks=[
                {"type": "heading", "content": "标题"},
                {"type": "bullet", "content": "X" * 120, "level": 1},
                {"type": "bullet", "content": "Y" * 90, "level": 1},
                {"type": "bullet", "content": "Z" * 90, "level": 1},
            ],
        )
        assert len(slide.text_blocks) == 4

    def test_heading_not_capped(self):
        slide = ContentSlideSchema(
            page_number=1,
            text_blocks=[
                {"type": "heading", "content": "X" * 200},
                {"type": "bullet", "content": "Y" * 40, "level": 0},
                {"type": "bullet", "content": "Z" * 40, "level": 0},
                {"type": "bullet", "content": "W" * 40, "level": 0},
            ],
        )
        assert len(slide.text_blocks) == 4

    def test_level_zero_not_capped(self):
        slide = ContentSlideSchema(
            page_number=1,
            text_blocks=[
                {"type": "bullet", "content": "X" * 200, "level": 0},
                {"type": "bullet", "content": "Y" * 40, "level": 0},
                {"type": "bullet", "content": "Z" * 40, "level": 0},
                {"type": "bullet", "content": "W" * 40, "level": 0},
            ],
        )
        assert len(slide.text_blocks) == 4
