"""
Pydantic schema contracts for pipeline stage boundaries.

Each agent's output is validated against these schemas before being passed downstream.
Six guarantees on ContentSlideSchema:
  1. infer_primary_visual — LLM often omits primary_visual; infer from actual visual fields
  2. enforce_visual_content_present — chart must have series/data, diagram must have type, vblock must have type+items
  3. enforce_visual_mutual_exclusion — only one of chart_suggestion/diagram_spec/visual_block may be non-null
  4. enforce_bullet_length_cap — Chinese text bullets ≤120 chars
  5. enforce_chart_data_traceability — chart numbers must appear in source text (H4)
  6. enforce_content_density — content slides must have ≥4 text_blocks and ≥300 chars total (H7)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationInfo, computed_field, model_validator

from models.slide_spec import NarrativeRole, PrimaryVisualType, SlideType


class ContentSlideSchema(BaseModel):
    page_number: int = Field(ge=1)
    slide_type: SlideType = SlideType.CONTENT
    takeaway_message: str = ""
    primary_visual: PrimaryVisualType = PrimaryVisualType.TEXT_ONLY
    text_blocks: list[dict] = Field(default_factory=list, min_length=4)
    chart_suggestion: Optional[dict] = None
    diagram_spec: Optional[dict] = None
    visual_block: Optional[dict] = None
    source_note: str = ""
    layout_hint: str = ""
    page_weight: Literal["hero", "pillar", "supporting", "transition"] = "pillar"
    is_failed: bool = False
    error_message: str = ""

    # -- Guarantee 1: infer primary_visual from actual visual fields --

    @model_validator(mode="before")
    @classmethod
    def infer_primary_visual(cls, data):
        if not isinstance(data, dict):
            return data
        pv = data.get("primary_visual")
        if not pv or pv == "text":
            if data.get("chart_suggestion"):
                data["primary_visual"] = "chart"
            elif data.get("diagram_spec"):
                data["primary_visual"] = "diagram"
            elif data.get("visual_block"):
                data["primary_visual"] = "visual_block"
            else:
                data["primary_visual"] = "text_only"
        return data

    # -- Guarantee 2: visual content must be non-empty --

    @model_validator(mode="after")
    def enforce_visual_content_present(self):
        if self.primary_visual == PrimaryVisualType.CHART:
            cs = self.chart_suggestion or {}
            series = cs.get("series") or cs.get("data")
            labels = cs.get("labels") or cs.get("categories")
            has_data = (isinstance(series, list) and series) or (
                isinstance(labels, list) and labels
            )
            if not has_data:
                raise ValueError(
                    f"P{self.page_number}: primary_visual=chart but chart_suggestion has no data"
                )
        elif self.primary_visual == PrimaryVisualType.DIAGRAM:
            ds = self.diagram_spec or {}
            if not ds.get("diagram_type"):
                raise ValueError(
                    f"P{self.page_number}: primary_visual=diagram but diagram_spec has no diagram_type"
                )
        elif self.primary_visual == PrimaryVisualType.VISUAL_BLOCK:
            vb = self.visual_block or {}
            if not vb.get("type"):
                raise ValueError(
                    f"P{self.page_number}: primary_visual=visual_block but visual_block has no type"
                )
            items = vb.get("items")
            if not isinstance(items, list) or not items:
                raise ValueError(
                    f"P{self.page_number}: visual_block type={vb.get('type')} but items is empty"
                )
        return self

    # -- Guarantee 3: mutual exclusion --

    @model_validator(mode="after")
    def enforce_visual_mutual_exclusion(self):
        pv = self.primary_visual
        has_chart = self.chart_suggestion is not None
        has_diag = self.diagram_spec is not None
        has_vb = self.visual_block is not None

        if pv == PrimaryVisualType.CHART and (has_diag or has_vb):
            raise ValueError(
                f"P{self.page_number}: primary_visual=chart but has diagram={has_diag} vblock={has_vb}"
            )
        elif pv == PrimaryVisualType.DIAGRAM and (has_chart or has_vb):
            raise ValueError(
                f"P{self.page_number}: primary_visual=diagram but has chart={has_chart} vblock={has_vb}"
            )
        elif pv == PrimaryVisualType.VISUAL_BLOCK and (has_chart or has_diag):
            raise ValueError(
                f"P{self.page_number}: primary_visual=visual_block but has chart={has_chart} diagram={has_diag}"
            )
        elif pv == PrimaryVisualType.TEXT_ONLY and (has_chart or has_diag or has_vb):
            raise ValueError(
                f"P{self.page_number}: primary_visual=text_only but visual fields present "
                f"(chart={has_chart} diagram={has_diag} vblock={has_vb})"
            )

        return self

    # -- Guarantee 4: bullet length cap (Chinese text ≤120 chars) --

    @model_validator(mode="after")
    def enforce_bullet_length_cap(self):
        overlong = []
        for tb in self.text_blocks:
            if not isinstance(tb, dict):
                continue
            content = tb.get("content", tb.get("text", ""))
            level = tb.get("level", 0)
            if level > 0 and len(content) > 150:
                overlong.append(len(content))
        if overlong:
            raise ValueError(
                f"P{self.page_number}: {len(overlong)} bullet(s) exceed 150 chars "
                f"(lengths: {overlong}). Max 150 chars per bullet. Rewrite shorter."
            )
        return self

    # -- Guarantee 6: content density (H7: ≥300 chars total) --

    @model_validator(mode="after")
    def enforce_content_density(self):
        if self.slide_type in ("title", "section_divider", "agenda"):
            return self
        if self.is_failed:
            return self
        total_chars = 0
        for tb in self.text_blocks:
            if not isinstance(tb, dict):
                continue
            content = tb.get("content", tb.get("text", ""))
            total_chars += len(content)
        if total_chars < 300:
            raise ValueError(
                f"P{self.page_number}: content density too low ({total_chars} chars, need ≥300). "
                f"Add more text_blocks or expand existing ones with specific data/examples."
            )
        return self

    # -- Guarantee 5: chart data traceability (H4) --

    @model_validator(mode="after")
    def enforce_chart_data_traceability(self, info: ValidationInfo):
        if self.primary_visual != PrimaryVisualType.CHART:
            return self
        cs = self.chart_suggestion or {}
        if cs.get("estimated") is True:
            return self

        ctx = info.context or {}
        raw_text = ctx.get("raw_text", "")
        tolerance = ctx.get("tolerance", 0.05)
        if not raw_text:
            return self

        chart_nums = self._extract_chart_numbers(cs)
        if not chart_nums:
            return self

        source_nums = self._extract_source_numbers(raw_text)
        untraceable = [n for n in chart_nums if not self._matches_source(n, source_nums, tolerance)]

        if untraceable:
            raise ValueError(
                f"P{self.page_number}: chart data traceability check failed — "
                f"numbers {untraceable} not found in source text (±{tolerance*100:.0f}% tolerance). "
                f"Either use source-verified numbers, or add \"estimated\": true to chart_suggestion "
                f"and prefix so_what with \"基于行业平均估算\"."
            )
        return self

    @staticmethod
    def _extract_chart_numbers(cs: dict) -> list[float]:
        nums: list[float] = []
        for s in (cs.get("series") or []):
            for v in (s.get("values") or []):
                if isinstance(v, (int, float)) and abs(v) > 0.01:
                    nums.append(float(v))
        so_what = cs.get("so_what", "") or ""
        for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:%|％)', so_what):
            val = float(m.group(1))
            if abs(val) > 0.01:
                nums.append(val)
        return nums

    @staticmethod
    def _extract_source_numbers(text: str) -> list[float]:
        nums: list[float] = []
        for m in re.finditer(r'(\d+(?:\.\d+)?)', text):
            val = float(m.group(1))
            if abs(val) > 0.01:
                nums.append(val)
        return nums

    @staticmethod
    def _matches_source(chart_val: float, source_nums: list[float], tolerance: float) -> bool:
        for src in source_nums:
            if abs(src) < 0.01:
                continue
            if abs(chart_val - src) / abs(src) <= tolerance:
                return True
        return False


class ContentResultSchema(BaseModel):
    slides: list[ContentSlideSchema] = Field(default_factory=list)

    @computed_field
    @property
    def total_pages(self) -> int:
        return len(self.slides)

    @computed_field
    @property
    def failed_pages(self) -> list[int]:
        return [s.page_number for s in self.slides if s.is_failed]


class OutlineItemSchema(BaseModel):
    page_number: int = Field(ge=1)
    slide_type: SlideType = SlideType.CONTENT
    takeaway_message: str = ""
    supporting_hint: str = ""
    data_source: str = ""
    primary_visual: PrimaryVisualType = PrimaryVisualType.TEXT_ONLY
    narrative_arc: NarrativeRole = NarrativeRole.EVIDENCE
    layout_hint: str = ""
    page_weight: Literal["hero", "pillar", "supporting", "transition"] = "pillar"
    section: str = ""
    title: str = ""
    chunk_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data):
        if not isinstance(data, dict):
            return data
        pv = data.get("primary_visual")
        if not pv or pv == "text":
            data["primary_visual"] = "text_only"
        na = data.get("narrative_arc", "")
        valid_arc = {e.value for e in NarrativeRole}
        if na not in valid_arc:
            data["narrative_arc"] = "evidence"
        return data


class OutlineResultSchema(BaseModel):
    narrative_logic: str = ""
    items: list[OutlineItemSchema] = Field(default_factory=list)
    data_gap_suggestions: list[str] = Field(default_factory=list)
    scqa: dict = {}
    root_claim: str = ""


@dataclass
class ParseResult:
    """Tagged result distinguishing JSON parse errors from schema validation errors."""

    schema: Optional[ContentSlideSchema] = None
    error_kind: Literal["ok", "json_parse", "schema"] = "ok"
    error_msg: str = ""
    raw_data: Optional[dict] = None
    raw_response: str = ""
