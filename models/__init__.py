"""
PPT Agent 核心数据模型
所有6层共享的统一数据结构，每层只填充自己管辖的字段
"""

from .slide_spec import (
    # Enums
    SlideType,
    NarrativeRole,
    ContentPattern,
    VisualBlockType,
    PrimaryVisualType,
    ChartType,
    DiagramNodeShape,
    ConnectorStyle,
    VisualEmphasis,

    # Layer 1: Input Parser
    TableData,
    ImageData,
    RawContent,

    # Layer 2: Content Analysis
    ContentElement,
    NarrativeSection,
    Narrative,

    # Layer 3-5: Data & Charts
    DataRef,
    ChartAnnotation,
    TrendLine,
    InsightSpec,
    ChartSpec,
    ChartSeries,

    # Layer 3-5: Diagrams
    DiagramNode,
    DiagramEdge,
    DiagramSpec,

    # Layer 3-5: Text
    TextBlock,

    # Visual Blocks
    VisualBlockItem,
    VisualBlock,

    # Layer 4: Visual Design
    BrandKit,
    VisualTheme,

    # Layer 6: Layout
    Rect,
    LayoutCoordinates,

    # Core
    SlideSpec,
    PresentationSpec,
)

from .model_config import StageModelConfig, PipelineModelConfig

__all__ = [
    # Enums
    "SlideType",
    "NarrativeRole",
    "ContentPattern",
    "VisualBlockType",
    "PrimaryVisualType",
    "ChartType",
    "DiagramNodeShape",
    "ConnectorStyle",
    "VisualEmphasis",

    # Layer 1
    "TableData",
    "ImageData",
    "RawContent",

    # Layer 2
    "ContentElement",
    "NarrativeSection",
    "Narrative",

    # Layer 3-5: Data & Charts
    "DataRef",
    "ChartAnnotation",
    "TrendLine",
    "InsightSpec",
    "ChartSpec",
    "ChartSeries",

    # Layer 3-5: Diagrams
    "DiagramNode",
    "DiagramEdge",
    "DiagramSpec",

    # Layer 3-5: Text
    "TextBlock",

    # Visual Blocks
    "VisualBlockItem",
    "VisualBlock",

    # Layer 4
    "BrandKit",
    "VisualTheme",

    # Layer 6
    "Rect",
    "LayoutCoordinates",

    # Core
    "SlideSpec",
    "PresentationSpec",

    # Model Config
    "StageModelConfig",
    "PipelineModelConfig",
]
