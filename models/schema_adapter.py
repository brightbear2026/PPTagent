"""
Bidirectional conversion between pipeline dicts and pydantic schemas.

Key design:
- Output (agent → orchestrator): schema.model_dump(mode="json") for JSON-safe dict
- Input (orchestrator → agent): schema_adapter.parse_slide() with tagged ParseResult
- Degradation: visual violations → degrade_to_text_only (preserve text_blocks, clear visuals)
- Placeholder: complete LLM failure → make_placeholder (minimal stub, is_failed=True)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from pydantic import ValidationError

from models.slide_spec import PrimaryVisualType
from models.schemas import (
    ContentResultSchema,
    ContentSlideSchema,
    OutlineItemSchema,
    ParseResult,
)

logger = logging.getLogger(__name__)


def degrade_to_text_only(raw_data: dict) -> ContentSlideSchema:
    """Schema violation but LLM text is salvageable → clear visuals, keep text_blocks."""
    cleaned = {
        **raw_data,
        "primary_visual": "text_only",
        "chart_suggestion": None,
        "diagram_spec": None,
        "visual_block": None,
        "is_failed": False,
        "error_message": "",
    }
    try:
        return ContentSlideSchema.model_validate(cleaned)
    except ValidationError:
        # Last resort: strip down to bare minimum with structural blocks
        blocks = raw_data.get("text_blocks", [])
        while len(blocks) < 4:
            blocks.append({"type": "bullet", "text": "", "level": 0})
        return ContentSlideSchema(
            page_number=raw_data.get("page_number", 0),
            slide_type=raw_data.get("slide_type", "content"),
            takeaway_message=raw_data.get("takeaway_message", ""),
            text_blocks=blocks,
            primary_visual=PrimaryVisualType.TEXT_ONLY,
            is_failed=True,
            error_message="degraded_from_schema_violation",
        )


def make_placeholder(
    page_number: int,
    slide_type: str = "content",
    title: str = "",
    takeaway: str = "",
) -> ContentSlideSchema:
    """LLM produced nothing → minimal placeholder stub."""
    return ContentSlideSchema(
        page_number=page_number,
        slide_type=slide_type,
        takeaway_message=takeaway,
        primary_visual=PrimaryVisualType.TEXT_ONLY,
        text_blocks=[
            {"type": "heading", "text": title or takeaway[:30]},
            {"type": "bullet", "text": takeaway, "level": 1},
            {"type": "bullet", "text": "", "level": 0},
            {"type": "bullet", "text": "", "level": 0},
        ],
        is_failed=True,
        error_message="content_generation_failed",
    )


def parse_slide(text: str, page_number: int, context: Optional[dict] = None) -> ParseResult:
    """Parse LLM output text into tagged ParseResult.

    Args:
        context: Optional ValidationContext dict (e.g. {"raw_text": ..., "tolerance": 0.05})
                 passed through to ContentSlideSchema.model_validate for chart traceability.

    Returns:
      - error_kind="ok" + schema instance on success
      - error_kind="json_parse" when no JSON can be extracted
      - error_kind="schema" + raw_data when JSON parses but fails schema validation
    """
    data = _extract_json(text, page_number)
    if data is None:
        return ParseResult(error_kind="json_parse", error_msg="no JSON found", raw_response=text)
    try:
        schema = ContentSlideSchema.model_validate(data, context=context)
        return ParseResult(schema=schema, error_kind="ok", raw_response=text)
    except ValidationError as e:
        return ParseResult(
            error_kind="schema",
            error_msg=str(e),
            raw_data=data,
            raw_response=text,
        )


def content_schema_to_dict(result: ContentResultSchema) -> dict:
    """Serialize ContentResultSchema to JSON-safe dict for orchestrator/storage."""
    return result.model_dump(mode="json")


def validate_outline(data: dict) -> list[str]:
    """Validate outline items, return list of error strings."""
    errors: list[str] = []
    items = data.get("items", data.get("slides", []))
    for item in items:
        try:
            OutlineItemSchema.model_validate(item)
        except ValidationError as e:
            pn = item.get("page_number", "?")
            for err in e.errors():
                errors.append(f"P{pn}: {err['msg']}")
    return errors


def _extract_json(text: str, page_number: int) -> Optional[dict]:
    """Extract first valid JSON object with 'text_blocks' from LLM output."""
    for pattern in [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
    ]:
        for match in re.finditer(pattern, text, re.DOTALL):
            try:
                data = json.loads(match.group(1).strip())
                if isinstance(data, dict) and "text_blocks" in data:
                    data.setdefault("page_number", page_number)
                    return data
            except Exception:
                continue

    try:
        start = text.find("{")
        if start >= 0:
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(text, start)
            if isinstance(data, dict) and "text_blocks" in data:
                data.setdefault("page_number", page_number)
                return data
    except Exception:
        pass

    return None
