"""VisualPlan schema — per-slide visual structure plan output by VisualPlannerAgent."""
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class EmphasisHint(BaseModel):
    highlight_field: Optional[str] = None
    accent_color: Optional[str] = None


class VisualPlan(BaseModel):
    """Per-slide visual structure plan."""

    page_number: int = Field(ge=1, description="1-based slide page number")
    layout_id: str = Field(description="Must be a name in LayoutRegistry.names()")
    layout_content: dict = Field(description="JSON matching the chosen layout's content_schema")
    emphasis: Optional[EmphasisHint] = None
    rationale: str = Field(min_length=10, max_length=200, description="Why this layout was chosen")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)

    @model_validator(mode="after")
    def validate_layout_content(self):
        from pipeline.layouts import LayoutRegistry

        if self.layout_id not in LayoutRegistry.names():
            raise ValueError(
                f"Unknown layout_id: '{self.layout_id}'. "
                f"Must be one of: {sorted(LayoutRegistry.names())}"
            )
        layout = LayoutRegistry.get(self.layout_id)
        layout.content_schema.model_validate(self.layout_content)
        return self


class VisualPlanResult(BaseModel):
    """Aggregate result from VisualPlannerAgent for all content slides."""

    plans: list[VisualPlan] = Field(default_factory=list)
    fallback_pages: list[int] = Field(
        default_factory=list,
        description="Pages where VisualPlanner failed and fell back to layout_hint",
    )
