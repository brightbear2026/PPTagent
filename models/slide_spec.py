"""
PPT Agent 核心数据模型

Pipeline阶段: parse → analyze → outline → content → build
每阶段只填充自己管辖的字段，数据通过SlideSpec向下传递
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4


# ============================================================
# 枚举定义
# ============================================================

class SlideType(str, Enum):
    TITLE = "title"
    AGENDA = "agenda"
    SECTION_DIVIDER = "section_divider"
    CONTENT = "content"
    DATA = "data"
    DIAGRAM = "diagram"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    MATRIX = "matrix"
    SUMMARY = "summary"
    APPENDIX = "appendix"


class NarrativeRole(str, Enum):
    """每页在整个叙事中的角色"""
    OPENING = "opening"           # 开篇引入
    PROBLEM = "problem_statement"  # 问题陈述
    CONTEXT = "context"           # 背景铺垫
    EVIDENCE = "evidence"         # 证据支撑
    ANALYSIS = "analysis"         # 分析论证
    COMPARISON = "comparison"     # 对比分析
    COUNTERPOINT = "counterpoint" # 反面论证/转折
    SOLUTION = "solution"         # 方案提出
    RECOMMENDATION = "recommendation"  # 建议
    CLOSING = "closing"           # 总结收尾


class ContentPattern(str, Enum):
    """内容结构模式 — 对应模板库第一级"""
    ARGUMENT_EVIDENCE = "argument_evidence"   # 论点 + 证据
    TWO_COLUMN = "two_column"                 # 双栏对比
    THREE_COLUMN = "three_column"             # 三栏并列
    LEFT_CHART_RIGHT_TEXT = "left_chart_right_text"
    LEFT_TEXT_RIGHT_CHART = "left_text_right_chart"
    MATRIX_2X2 = "matrix_2x2"                # 2x2象限
    TIMELINE_HORIZONTAL = "timeline_horizontal"
    PROCESS_FLOW = "process_flow"             # 流程图
    DATA_DASHBOARD = "data_dashboard"         # 上文下图
    FULL_TABLE = "full_table"                 # 纯表格
    TITLE_ONLY = "title_only"                 # 标题页
    AGENDA_LIST = "agenda_list"               # 目录/议程
    KPI_HIGHLIGHT = "kpi_highlight"           # KPI卡片仪表盘
    STEP_FLOW = "step_flow"                   # 步骤/流程卡片
    ICON_GRID = "icon_grid"                   # 图标+文字网格
    STAT_CALLOUT = "stat_callout"             # 核心数据+引用


class VisualBlockType(str, Enum):
    """可视化块类型 — 文字内容的可视化呈现形式"""
    BULLET_LIST = "bullet_list"               # 层级论述（向下兼容）
    KPI_CARDS = "kpi_cards"                   # 2-4个关键指标卡片
    COMPARISON_COLUMNS = "comparison_columns" # A vs B 对比栏
    STEP_CARDS = "step_cards"                 # 3-6个步骤/流程卡片
    ICON_TEXT_GRID = "icon_text_grid"         # 图标+标题+描述网格
    STAT_HIGHLIGHT = "stat_highlight"         # 单个核心数据高亮
    CALLOUT_BOX = "callout_box"              # 关键洞察/引用框


class PrimaryVisualType(str, Enum):
    """每页的主视觉类型 — 互斥，每页只能选一种"""
    CHART = "chart"
    DIAGRAM = "diagram"
    VISUAL_BLOCK = "visual_block"
    TEXT_ONLY = "text_only"


@dataclass
class VisualBlockItem:
    """可视化块中的单个条目"""
    title: str = ""
    value: str = ""
    description: str = ""
    trend: str = ""           # "up" / "down" / "" — 用于KPI
    icon_shape: str = ""      # MSO_SHAPE名 — 用于icon_text_grid
    color: str = ""           # 条目特定颜色覆盖


@dataclass
class VisualBlock:
    """可视化块 — 描述一组内容应以何种可视化形式呈现"""
    block_type: VisualBlockType = VisualBlockType.BULLET_LIST
    items: list[VisualBlockItem] = field(default_factory=list)
    columns: int = 0          # 网格列数，0=自动
    heading: str = ""         # 块标题（可选）

    def to_dict(self) -> dict:
        return {
            "block_type": self.block_type.value,
            "items": [
                {k: v for k, v in {
                    "title": it.title, "value": it.value,
                    "description": it.description, "trend": it.trend,
                    "icon_shape": it.icon_shape, "color": it.color,
                }.items() if v}
                for it in self.items
            ],
            "columns": self.columns,
            "heading": self.heading,
        }

    @classmethod
    def from_dict(cls, data: dict) -> VisualBlock:
        try:
            # LLM may output "type" while internal format uses "block_type"
            raw_type = data.get("block_type") or data.get("type", "bullet_list")
            bt = VisualBlockType(raw_type)
        except ValueError:
            bt = VisualBlockType.BULLET_LIST
        items = [
            VisualBlockItem(
                title=it.get("title", ""),
                value=it.get("value", ""),
                description=it.get("description", ""),
                trend=it.get("trend", ""),
                icon_shape=it.get("icon_shape", ""),
                color=it.get("color", ""),
            )
            for it in data.get("items", [])
        ]
        return cls(
            block_type=bt,
            items=items,
            columns=data.get("columns", 0),
            heading=data.get("heading", ""),
        )


class ChartType(str, Enum):
    BAR = "bar"
    COLUMN = "column"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    AREA = "area"
    WATERFALL = "waterfall"
    COMBO = "combo"  # 组合图（柱+线）


class DiagramNodeShape(str, Enum):
    RECTANGLE = "rectangle"
    ROUNDED_RECT = "rounded_rectangle"
    CIRCLE = "circle"
    DIAMOND = "diamond"
    PARALLELOGRAM = "parallelogram"
    CYLINDER = "cylinder"  # 数据库


class ConnectorStyle(str, Enum):
    STRAIGHT = "straight"
    ELBOW = "elbow"
    CURVED = "curved"


class VisualEmphasis(str, Enum):
    BOLD_COLOR = "bold_color"
    ANNOTATION = "annotation"
    HIGHLIGHT_BG = "highlight_bg"
    CALLOUT = "callout"


# ============================================================
# 输入解析层（第1层）输出
# ============================================================

@dataclass
class TableData:
    headers: list[str]
    rows: list[list[str | float | None]]
    source_sheet: str = ""
    source_range: str = ""


@dataclass
class ImageData:
    file_path: str
    width_px: int = 0
    height_px: int = 0
    description: str = ""


@dataclass
class SourcePage:
    """原文中检测到的页面/章节"""
    title: str                    # 页面标题
    content: str                  # 页面正文
    page_number: int = 0          # 页码


@dataclass
class StructuredSection:
    """文档层级结构中的一个章节（用于结构化解析）"""
    title: str                              # 章节标题
    level: int                              # 层级深度：1=顶级, 2=子节, 3=三级
    content: str                            # 章节正文（不含子节内容）
    children: list[StructuredSection] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    char_count: int = 0                     # 章节正文字符数
    source_page_number: int = 0             # 原文页码（如果有）

    def total_char_count(self) -> int:
        """包含子节的总字符数"""
        total = self.char_count
        for child in self.children:
            total += child.total_char_count()
        return total

    def flatten(self) -> list[StructuredSection]:
        """展平为线性的章节列表（深度优先）"""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "level": self.level,
            "content": self.content,
            "children": [c.to_dict() for c in self.children],
            "tables": [
                {"headers": t.headers, "rows": t.rows, "source_sheet": t.source_sheet}
                for t in self.tables
            ],
            "char_count": self.char_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> StructuredSection:
        return cls(
            title=d.get("title", ""),
            level=d.get("level", 1),
            content=d.get("content", ""),
            children=[cls.from_dict(c) for c in d.get("children", [])],
            tables=[
                TableData(headers=t["headers"], rows=t["rows"],
                          source_sheet=t.get("source_sheet", ""))
                for t in d.get("tables", [])
            ],
            char_count=d.get("char_count", 0),
        )


@dataclass
class RawContent:
    """第1层输出：统一的原始内容对象"""
    source_type: str              # "doc", "excel", "text", "ppt"
    raw_text: str = ""
    tables: list[TableData] = field(default_factory=list)
    images: list[ImageData] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    detected_language: str = "zh"  # "zh" | "en" | "mixed"
    source_pages: list[SourcePage] = field(default_factory=list)  # 检测到的页面结构
    is_structured: bool = False     # 原文是否已按页/章节组织
    structured_sections: list[StructuredSection] = field(default_factory=list)  # 层级章节树


# ============================================================
# 内容分析层（第2层）输出
# ============================================================

@dataclass
class ContentElement:
    """提取的单个内容元素"""
    element_type: str   # "fact", "data", "opinion", "conclusion"
    content: str
    source: str = ""    # 来源标注
    confidence: float = 1.0
    topics: list[str] = field(default_factory=list)
    related_data: Optional[TableData] = None


@dataclass
class NarrativeSection:
    """叙事结构中的一个段落"""
    core_argument: str            # 核心论点
    role: NarrativeRole           # 在叙事中的角色
    supporting_elements: list[ContentElement] = field(default_factory=list)
    transition_to_next: str = ""  # 到下一段的过渡逻辑


@dataclass
class Narrative:
    """第2层输出：完整的叙事结构"""
    title: str
    executive_summary: str
    sections: list[NarrativeSection]
    target_audience: str = ""
    overall_tone: str = "professional"


# ============================================================
# 数据与图表规格
# ============================================================

@dataclass
class DataRef:
    """数据源引用"""
    source_id: str
    table: Optional[TableData] = None
    description: str = ""
    key_metrics: list[str] = field(default_factory=list)


@dataclass
class ChartAnnotation:
    """图表标注"""
    text: str
    target_data_point: str = ""  # 指向的数据点标识
    position: str = "auto"       # "auto", "above", "below", "left", "right"


@dataclass
class TrendLine:
    type: str = "linear"  # "linear", "moving_avg", "target"
    label: str = ""
    value: Optional[float] = None  # 用于target线


@dataclass
class InsightSpec:
    """数据洞察"""
    data_point: tuple[str, float]    # ("Q3", 85)
    insight_text: str                # "同比增长32%"
    emphasis: VisualEmphasis = VisualEmphasis.ANNOTATION


@dataclass
class ChartSpec:
    """图表完整规格"""
    chart_id: str = field(default_factory=lambda: f"chart_{uuid4().hex[:8]}")
    chart_type: ChartType = ChartType.COLUMN
    data_ref: Optional[DataRef] = None

    # 数据
    categories: list[str] = field(default_factory=list)    # X轴标签
    series: list[ChartSeries] = field(default_factory=list)

    # 叙事层（第5层填充）
    so_what: str = ""                                       # 这张图的结论
    key_insights: list[InsightSpec] = field(default_factory=list)
    annotations: list[ChartAnnotation] = field(default_factory=list)
    trend_lines: list[TrendLine] = field(default_factory=list)

    # 样式
    title: str = ""
    show_legend: bool = True
    show_data_labels: bool = False
    color_override: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ChartSpec":
        if isinstance(data.get("chart_type"), str):
            try:
                data["chart_type"] = ChartType(data["chart_type"])
            except ValueError:
                data["chart_type"] = ChartType.COLUMN
        if isinstance(data.get("series"), list):
            data["series"] = [
                ChartSeries(**s) if isinstance(s, dict) else s
                for s in data["series"]
            ]
        # 清理不存在的字段
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        data = {k: v for k, v in data.items() if k in valid}
        return cls(**data)


@dataclass
class ChartSeries:
    """图表数据系列"""
    name: str
    values: list[float]
    color: str = ""


# ============================================================
# 拓扑图/架构图规格
# ============================================================

@dataclass
class DiagramNode:
    node_id: str
    label: str
    shape: DiagramNodeShape = DiagramNodeShape.ROUNDED_RECT
    sublabel: str = ""
    icon: str = ""       # 预定义图标名
    group: str = ""      # 分组/泳道
    color: str = ""      # 留空则用主题色


@dataclass
class DiagramEdge:
    from_id: str
    to_id: str
    label: str = ""
    style: ConnectorStyle = ConnectorStyle.ELBOW
    bidirectional: bool = False


@dataclass
class DiagramSpec:
    """拓扑图/架构图完整规格"""
    diagram_id: str = field(default_factory=lambda: f"diag_{uuid4().hex[:8]}")
    diagram_type: str = "topology"  # "topology", "flowchart", "org_chart", "architecture"
    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)
    layout_direction: str = "TB"   # "TB", "LR", "BT", "RL"
    title: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "DiagramSpec":
        if isinstance(data.get("nodes"), list):
            for n in data["nodes"]:
                if isinstance(n, dict) and isinstance(n.get("shape"), str):
                    try:
                        n["shape"] = DiagramNodeShape(n["shape"])
                    except ValueError:
                        n["shape"] = DiagramNodeShape.ROUNDED_RECT
            data["nodes"] = [DiagramNode(**n) if isinstance(n, dict) else n for n in data["nodes"]]
        if isinstance(data.get("edges"), list):
            for e in data["edges"]:
                if isinstance(e, dict) and isinstance(e.get("style"), str):
                    try:
                        e["style"] = ConnectorStyle(e["style"])
                    except ValueError:
                        e["style"] = ConnectorStyle.ELBOW
            data["edges"] = [DiagramEdge(**e) if isinstance(e, dict) else e for e in data["edges"]]
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        data = {k: v for k, v in data.items() if k in valid}
        return cls(**data)


# ============================================================
# 文本块
# ============================================================

@dataclass
class TextBlock:
    """页面上的一个文本区域"""
    block_id: str = field(default_factory=lambda: f"txt_{uuid4().hex[:8]}")
    content: str = ""
    level: int = 0           # 0=正文, 1=子弹点L1, 2=子弹点L2
    is_bold: bool = False
    is_footnote: bool = False
    font_size_pt: Optional[float] = None  # None则用模板默认值


# ============================================================
# 视觉主题与品牌
# ============================================================

@dataclass
class BrandKit:
    """用户品牌包"""
    logo_path: str = ""
    primary_color: str = "#003D6E"
    secondary_color: str = "#FF6B35"
    accent_color: str = "#00A878"
    title_font: str = "Arial"
    body_font: str = "Calibri"
    logo_position: str = "bottom_right"  # "bottom_right", "top_left", "title_center"


@dataclass
class VisualTheme:
    """视觉主题（模板库第二级）"""
    theme_id: str = "consulting_formal"
    colors: dict = field(default_factory=lambda: {
        "primary": "#003D6E",
        "secondary": "#005A9E",
        "accent": "#FF6B35",
        "text_dark": "#2D3436",
        "text_light": "#636E72",
        "background": "#FFFFFF",
        "chart_palette": ["#003D6E", "#FF6B35", "#00A878", "#E17055", "#6C5CE7"],
    })
    fonts: dict = field(default_factory=lambda: {
        "title": "Arial",
        "subtitle": "Arial",
        "body": "Calibri",
        "footnote": "Calibri",
    })
    font_sizes: dict = field(default_factory=lambda: {
        "title": 28,
        "subtitle": 18,
        "body": 12,
        "bullet": 11,
        "footnote": 8,
        "chart_title": 14,
        "chart_label": 9,
    })

    def apply_brand(self, brand: BrandKit) -> VisualTheme:
        """用品牌包覆盖默认主题"""
        self.colors["primary"] = brand.primary_color
        self.colors["accent"] = brand.secondary_color
        self.colors["chart_palette"][0] = brand.primary_color
        self.colors["chart_palette"][1] = brand.secondary_color
        self.fonts["title"] = brand.title_font
        self.fonts["body"] = brand.body_font
        return self


# ============================================================
# 布局坐标
# ============================================================

@dataclass
class Rect:
    """矩形区域，单位: EMU (English Metric Units, pptx原生单位)"""
    left: int
    top: int
    width: int
    height: int


@dataclass
class LayoutCoordinates:
    """一页的所有元素坐标"""
    title_area: Optional[Rect] = None
    takeaway_area: Optional[Rect] = None
    body_areas: list[Rect] = field(default_factory=list)      # 文本区域
    chart_areas: list[Rect] = field(default_factory=list)      # 图表区域
    diagram_areas: list[Rect] = field(default_factory=list)    # 拓扑图区域
    picture_areas: list[Rect] = field(default_factory=list)    # 原材料图片区域
    visual_block_areas: list[Rect] = field(default_factory=list)  # 可视化块独立slot坐标
    footnote_area: Optional[Rect] = None
    logo_area: Optional[Rect] = None

    @classmethod
    def from_dict(cls, data: dict) -> "LayoutCoordinates":
        def to_rect(d):
            return Rect(**d) if isinstance(d, dict) else d
        data = dict(data)
        for attr in ("title_area", "takeaway_area", "footnote_area", "logo_area"):
            if attr in data and isinstance(data[attr], dict):
                data[attr] = to_rect(data[attr])
        for attr in ("body_areas", "chart_areas", "diagram_areas", "picture_areas", "visual_block_areas"):
            if attr in data and isinstance(data[attr], list):
                data[attr] = [to_rect(r) for r in data[attr]]
        return cls(**data)
    source_area: Optional[Rect] = None  # 数据来源标注


# ============================================================
# SlideSpec — 核心对象
# ============================================================

@dataclass
class SlideSpec:
    """
    贯穿整个6层流水线的核心数据对象。
    每层只填充自己管辖的字段，其余字段保持None/空。
    """
    # 标识
    slide_id: str = field(default_factory=lambda: f"slide_{uuid4().hex[:8]}")
    slide_index: int = 0
    slide_type: SlideType = SlideType.CONTENT

    # ── 第2层填充：内容分析 ──
    takeaway_message: str = ""          # 核心论点（页面最重要的一句话）
    sub_takeaway: str = ""              # 副论点/补充结论（可选）
    narrative_arc: NarrativeRole = NarrativeRole.EVIDENCE
    supporting_elements: list[ContentElement] = field(default_factory=list)
    data_references: list[DataRef] = field(default_factory=list)
    key_insights: list[str] = field(default_factory=list)  # 关键洞察列表

    # ── 第3层填充：结构规划 ──
    text_blocks: list[TextBlock] = field(default_factory=list)
    source_note: str = ""               # 数据来源脚注
    language: str = "zh"                # "zh" / "en" / "mixed"，影响字号策略

    # ── 章节归属 ──
    section_id: str = ""                # 所属章节 id（用于过渡页关联）
    section_name: str = ""              # 所属章节名称

    # ── 可视化块（content阶段填充，驱动第4层版式选择）──
    visual_block: Optional[VisualBlock] = None
    primary_visual: str = ""            # PrimaryVisualType值，互斥控制

    # ── 第4层填充：视觉设计 ──
    content_pattern: Optional[ContentPattern] = None
    visual_theme: Optional[VisualTheme] = None
    layout_template_id: str = ""

    # ── 第5层填充：图表生成 ──
    charts: list[ChartSpec] = field(default_factory=list)
    diagrams: list[DiagramSpec] = field(default_factory=list)

    # ── 原材料图片（从 Layer1 分发下来，文件路径字符串列表）──
    pictures: list[str] = field(default_factory=list)

    # ── 第6层填充：布局计算 + 输出 ──
    layout: Optional[LayoutCoordinates] = None

    # ── 元数据 ──
    is_dirty: bool = False              # 脏标记
    dirty_layers: list[int] = field(default_factory=list)  # 需要重新跑的层

    def mark_dirty(self, from_layer: int = 3):
        self.is_dirty = True
        self.dirty_layers = list(range(from_layer, 7))

    def clear_dirty(self):
        self.is_dirty = False
        self.dirty_layers = []

    def to_dict(self) -> dict:
        """序列化为JSON安全的dict"""
        from dataclasses import asdict
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SlideSpec":
        """从dict反序列化"""
        # 处理 enum 字段
        if "slide_type" in data and isinstance(data["slide_type"], str):
            try:
                data["slide_type"] = SlideType(data["slide_type"])
            except ValueError:
                data["slide_type"] = SlideType.CONTENT
        if "narrative_arc" in data and isinstance(data["narrative_arc"], str):
            try:
                data["narrative_arc"] = NarrativeRole(data["narrative_arc"])
            except ValueError:
                data["narrative_arc"] = NarrativeRole.EVIDENCE
        if "content_pattern" in data and isinstance(data["content_pattern"], str) and data["content_pattern"]:
            try:
                data["content_pattern"] = ContentPattern(data["content_pattern"])
            except ValueError:
                data["content_pattern"] = None

        # 处理嵌套 dataclass 列表
        if "text_blocks" in data and isinstance(data["text_blocks"], list):
            data["text_blocks"] = [
                TextBlock(**tb) if isinstance(tb, dict) else tb
                for tb in data["text_blocks"]
            ]
        if "charts" in data and isinstance(data["charts"], list):
            data["charts"] = [
                ChartSpec.from_dict(c) if isinstance(c, dict) else c
                for c in data["charts"]
            ]
        if "diagrams" in data and isinstance(data["diagrams"], list):
            data["diagrams"] = [
                DiagramSpec.from_dict(d) if isinstance(d, dict) else d
                for d in data["diagrams"]
            ]
        if "visual_block" in data and isinstance(data["visual_block"], dict):
            data["visual_block"] = VisualBlock.from_dict(data["visual_block"])

        # 处理 visual_theme（dict → VisualTheme）
        if "visual_theme" in data and isinstance(data["visual_theme"], dict):
            data["visual_theme"] = VisualTheme(**data["visual_theme"])

        # 处理 layout_coordinates
        if "layout" in data and isinstance(data["layout"], dict):
            data["layout"] = LayoutCoordinates.from_dict(data["layout"])

        # 清理未知字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**data)


# ============================================================
# Presentation — 整个PPT
# ============================================================

@dataclass
class PresentationSpec:
    """整个PPT的顶层规格"""
    title: str = ""
    subtitle: str = ""
    author: str = ""
    created_at: str = ""

    slides: list[SlideSpec] = field(default_factory=list)
    theme: VisualTheme = field(default_factory=VisualTheme)
    brand: Optional[BrandKit] = None
    language: str = "zh"  # "zh", "en", "mixed"

    # 生成配置
    target_slide_count: int = 0     # 0 = 自动决定
    max_slides: int = 50
    quality_level: str = "high"     # "draft", "standard", "high"

    def apply_brand_if_present(self):
        if self.brand:
            self.theme.apply_brand(self.brand)

    def to_dict(self) -> dict:
        """序列化为JSON安全的dict"""
        from dataclasses import asdict
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PresentationSpec":
        """从dict反序列化"""
        if "slides" in data and isinstance(data["slides"], list):
            data["slides"] = [
                SlideSpec.from_dict(s) if isinstance(s, dict) else s
                for s in data["slides"]
            ]
        if "theme" in data and isinstance(data["theme"], dict):
            data["theme"] = VisualTheme(**data["theme"])
        if "brand" in data and isinstance(data["brand"], dict):
            data["brand"] = BrandKit(**data["brand"])
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        data = {k: v for k, v in data.items() if k in valid}
        return cls(**data)


# ============================================================
# 数据分析层（analyze阶段）输出
# ============================================================

class MetricType(str, Enum):
    """派生指标类型"""
    YOY_GROWTH = "yoy_growth"           # 同比增长率
    QOQ_GROWTH = "qoq_growth"           # 环比增长率
    CAGR = "cagr"                       # 年复合增长率
    TOTAL = "total"                     # 合计
    AVERAGE = "average"                 # 平均值
    MAX = "max"                         # 最大值
    MIN = "min"                         # 最小值
    RATIO = "ratio"                     # 占比
    RANK = "rank"                       # 排名
    STDDEV = "stddev"                   # 标准差
    HHI = "hhi"                         # 赫芬达尔指数(集中度)
    TREND = "trend"                     # 趋势方向


@dataclass
class DerivedMetric:
    """数据分析阶段计算的派生指标"""
    metric_type: MetricType
    name: str                           # 可读名称 e.g. "2024年收入同比增长率"
    value: float
    formatted_value: str = ""           # 格式化后 e.g. "32.0%", "15.6亿"
    source_table: str = ""              # 来源表格/Sheet名
    source_column: str = ""             # 来源列名
    context: str = ""                   # 上下文说明 e.g. "相比2023年12.0亿"


@dataclass
class DataGapSuggestion:
    """数据gap识别结果 — 建议用户补充的数据"""
    gap_description: str                # e.g. "行业平均增长率"
    reason: str                         # e.g. "无法判断32%增长是否优于行业"
    importance: str = "medium"          # "high", "medium", "low"
    related_pages: list[int] = field(default_factory=list)  # 影响的页码


@dataclass
class EnrichedTableData:
    """增强后的表格数据（原始表格+派生列）"""
    original: TableData
    derived_columns: dict = field(default_factory=dict)  # col_name -> list[values]
    summary: dict = field(default_factory=dict)           # col_name -> {total, avg, max, min}


@dataclass
class ValidationWarning:
    """数据一致性校验警告"""
    message: str                        # e.g. "正文提到收入15.6亿，但表格合计15.3亿"
    text_value: str = ""                # 正文中的数字
    table_value: str = ""               # 表格中的数字
    severity: str = "warning"           # "warning", "error"


@dataclass
class StrategyInsight:
    """analyze阶段LLM策略分析输出 — 指导outline生成的核心框架"""
    document_summary: str = ""             # LLM生成的文档概要（3-5句话）
    audience_analysis: str = ""            # 目标受众关注点分析
    scenario_strategy: str = ""            # 针对该汇报场景的叙事策略
    core_themes: list[str] = field(default_factory=list)       # 核心主题列表（3-7个）
    recommended_structure: str = ""        # 推荐的叙事框架（如SCR/SCQA/Issue Tree）
    recommended_page_range: str = ""       # 推荐页数范围（如"15-20页"）
    key_messages: list[str] = field(default_factory=list)      # 核心论点（3-5个）
    visual_style: str = ""                 # 视觉风格（consulting_formal/tech_modern/business_minimalist/finance_stable/creative_vibrant）


@dataclass
class AnalysisResult:
    """analyze阶段完整输出"""
    # LLM策略分析（必须 — 指导outline的核心框架）
    strategy: StrategyInsight = field(default_factory=StrategyInsight)
    # 数据分析
    derived_metrics: list[DerivedMetric] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)              # LLM提取的关键发现
    data_gaps: list[DataGapSuggestion] = field(default_factory=list)
    validation_warnings: list[ValidationWarning] = field(default_factory=list)
    enriched_tables: list[EnrichedTableData] = field(default_factory=list)

    def to_dict(self) -> dict:
        """序列化为可存储的dict"""
        s = self.strategy
        return {
            "strategy": {
                "document_summary": s.document_summary,
                "audience_analysis": s.audience_analysis,
                "scenario_strategy": s.scenario_strategy,
                "core_themes": s.core_themes,
                "recommended_structure": s.recommended_structure,
                "recommended_page_range": s.recommended_page_range,
                "key_messages": s.key_messages,
            },
            "derived_metrics": [
                {"metric_type": m.metric_type.value, "name": m.name,
                 "value": m.value, "formatted_value": m.formatted_value,
                 "source_table": m.source_table, "source_column": m.source_column,
                 "context": m.context}
                for m in self.derived_metrics
            ],
            "key_findings": self.key_findings,
            "data_gaps": [
                {"gap_description": g.gap_description, "reason": g.reason,
                 "importance": g.importance, "related_pages": g.related_pages}
                for g in self.data_gaps
            ],
            "validation_warnings": [
                {"message": w.message, "text_value": w.text_value,
                 "table_value": w.table_value, "severity": w.severity}
                for w in self.validation_warnings
            ],
            "enriched_tables": [
                {
                    "original": {
                        "headers": et.original.headers,
                        "rows": et.original.rows,
                        "source_sheet": et.original.source_sheet,
                    },
                    "summary": et.summary,
                }
                for et in self.enriched_tables
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> AnalysisResult:
        """从dict反序列化"""
        # 反序列化 strategy
        sd = data.get("strategy", {})
        strategy = StrategyInsight(
            document_summary=sd.get("document_summary", ""),
            audience_analysis=sd.get("audience_analysis", ""),
            scenario_strategy=sd.get("scenario_strategy", ""),
            core_themes=sd.get("core_themes", []),
            recommended_structure=sd.get("recommended_structure", ""),
            recommended_page_range=sd.get("recommended_page_range", ""),
            key_messages=sd.get("key_messages", []),
        )

        return cls(
            strategy=strategy,
            derived_metrics=[
                DerivedMetric(
                    metric_type=MetricType(m["metric_type"]), name=m["name"],
                    value=m["value"], formatted_value=m.get("formatted_value", ""),
                    source_table=m.get("source_table", ""),
                    source_column=m.get("source_column", ""),
                    context=m.get("context", ""))
                for m in data.get("derived_metrics", [])
            ],
            key_findings=data.get("key_findings", []),
            data_gaps=[
                DataGapSuggestion(
                    gap_description=g["gap_description"], reason=g["reason"],
                    importance=g.get("importance", "medium"),
                    related_pages=g.get("related_pages", []))
                for g in data.get("data_gaps", [])
            ],
            validation_warnings=[
                ValidationWarning(
                    message=w["message"], text_value=w.get("text_value", ""),
                    table_value=w.get("table_value", ""),
                    severity=w.get("severity", "warning"))
                for w in data.get("validation_warnings", [])
            ],
            enriched_tables=[
                EnrichedTableData(
                    original=TableData(
                        headers=et["original"]["headers"],
                        rows=et["original"]["rows"],
                        source_sheet=et["original"].get("source_sheet", ""),
                    ),
                    summary=et.get("summary", {}),
                )
                for et in data.get("enriched_tables", [])
                if isinstance(et, dict) and "original" in et
            ],
        )


# ============================================================
# 大纲层（outline阶段）输出
# ============================================================

@dataclass
class OutlineItem:
    """大纲中的一页"""
    page_number: int
    slide_type: str                     # SlideType值: "title", "content", "data", etc.
    takeaway_message: str               # 该页核心论点
    supporting_hint: str = ""           # 该页需要什么支撑材料
    data_source: str = ""               # 引用的数据来源 e.g. "Sheet1: 季度收入表"
    primary_visual: str = ""            # PrimaryVisualType值: "chart"/"diagram"/"visual_block"/"text_only"
    narrative_arc: str = ""             # NarrativeRole值，由 OutlineAgent LLM 直接填写
    chunk_ids: list = field(default_factory=list)  # 精确绑定的原文 chunk id 列表


@dataclass
class OutlineResult:
    """outline阶段完整输出"""
    narrative_logic: str = ""           # 整体叙事逻辑 e.g. "SCR: ...(S)→...(C)→...(R)"
    items: list[OutlineItem] = field(default_factory=list)
    data_gap_suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "narrative_logic": self.narrative_logic,
            "items": [
                {"page_number": i.page_number, "slide_type": i.slide_type,
                 "takeaway_message": i.takeaway_message,
                 "supporting_hint": i.supporting_hint,
                 "data_source": i.data_source,
                 "primary_visual": i.primary_visual,
                 "narrative_arc": i.narrative_arc}
                for i in self.items
            ],
            "data_gap_suggestions": self.data_gap_suggestions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> OutlineResult:
        return cls(
            narrative_logic=data.get("narrative_logic", ""),
            items=[
                OutlineItem(
                    page_number=i["page_number"], slide_type=i["slide_type"],
                    takeaway_message=i["takeaway_message"],
                    supporting_hint=i.get("supporting_hint", ""),
                    data_source=i.get("data_source", ""),
                    primary_visual=i.get("primary_visual", ""),
                    narrative_arc=i.get("narrative_arc", ""))
                for i in data.get("items", [])
            ],
            data_gap_suggestions=data.get("data_gap_suggestions", []),
        )


# ============================================================
# 内容填充层（content阶段）输出 — 扩展ChartSuggestion
# ============================================================

@dataclass
class ChartSuggestion:
    """LLM建议的图表（content阶段输出，build阶段转为ChartSpec）"""
    chart_type: str = "column"          # ChartType值
    data_feature: str = ""              # 数据特征 e.g. "time_series", "composition"
    title: str = ""
    categories: list[str] = field(default_factory=list)
    series: list[dict] = field(default_factory=list)  # [{"name": "...", "values": [...]}]
    so_what: str = ""                   # 图表结论


# ============================================================
# 概念图表规格（content阶段LLM智能生成）
# ============================================================

class DiagramType(str, Enum):
    """内容驱动型图表类型"""
    PROCESS_FLOW = "process_flow"       # 流程/步骤图
    ARCHITECTURE = "architecture"       # 架构/层级图
    RELATIONSHIP = "relationship"       # 关系/因果图
    FRAMEWORK = "framework"             # 框架/矩阵图


@dataclass
class ProcessFlowSpec:
    """流程图规格"""
    direction: str = "horizontal"       # "horizontal", "vertical"
    nodes: list[dict] = field(default_factory=list)
    # [{"id": "1", "label": "调研", "desc": "市场调研3个月"}]
    connections: list[dict] = field(default_factory=list)
    # [{"from": "1", "to": "2", "label": "Q1完成"}]


@dataclass
class ArchitectureSpec:
    """架构图规格"""
    variant: str = "layers"             # "layers", "tree"
    # layers variant:
    layers: list[dict] = field(default_factory=list)
    # [{"label": "前端", "items": ["Web", "Mobile"]}]
    cross_cutting: list[str] = field(default_factory=list)  # 贯穿各层的组件
    # tree variant:
    root: dict = field(default_factory=dict)
    # {"label": "CEO", "children": [{"label": "CTO", "children": [...]}]}


@dataclass
class RelationshipSpec:
    """关系图规格"""
    variant: str = "causal"             # "causal", "network", "ecosystem"
    nodes: list[dict] = field(default_factory=list)
    # [{"id": "1", "label": "原材料涨价", "role": "cause"}]
    edges: list[dict] = field(default_factory=list)
    # [{"from": "1", "to": "3", "label": "+30%", "type": "directed"}]


@dataclass
class FrameworkSpec:
    """框架图规格"""
    variant: str = "matrix_2x2"         # "matrix_2x2", "swot", "pyramid", "venn", "funnel"
    # matrix_2x2:
    x_axis: dict = field(default_factory=dict)  # {"label": "成本", "low": "低", "high": "高"}
    y_axis: dict = field(default_factory=dict)
    quadrants: list[dict] = field(default_factory=list)
    # [{"position": "top_left", "label": "速赢", "items": ["项目A"]}]
    # swot:
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    threats: list[str] = field(default_factory=list)
    # pyramid:
    pyramid_levels: list[dict] = field(default_factory=list)
    # [{"label": "战略", "desc": "..."}] — top to bottom
    # funnel:
    funnel_stages: list[dict] = field(default_factory=list)
    # [{"label": "访问", "value": 10000}]
    # venn:
    circles: list[dict] = field(default_factory=list)
    # [{"label": "A", "items": ["x"]}, ...], intersection items in overlap field
    intersection: list[str] = field(default_factory=list)


@dataclass
class ContentDiagramSpec:
    """内容驱动型图表统一规格（content阶段LLM输出）"""
    diagram_type: DiagramType
    title: str = ""

    # 具体规格（根据diagram_type只填充一个）
    process_flow: Optional[ProcessFlowSpec] = None
    architecture: Optional[ArchitectureSpec] = None
    relationship: Optional[RelationshipSpec] = None
    framework: Optional[FrameworkSpec] = None

    @classmethod
    def from_dict(cls, data: dict) -> ContentDiagramSpec:
        try:
            dtype = DiagramType(data["diagram_type"])
        except (ValueError, KeyError):
            # LLM returned an unknown diagram_type; map common aliases or use process_flow
            raw = str(data.get("diagram_type", "")).lower()
            _alias = {
                "hierarchy": DiagramType.ARCHITECTURE,
                "org_chart": DiagramType.ARCHITECTURE,
                "flowchart": DiagramType.PROCESS_FLOW,
                "flow": DiagramType.PROCESS_FLOW,
                "comparison": DiagramType.FRAMEWORK,
                "matrix": DiagramType.FRAMEWORK,
                "causal": DiagramType.RELATIONSHIP,
            }
            dtype = _alias.get(raw, DiagramType.PROCESS_FLOW)
        spec = cls(diagram_type=dtype, title=data.get("title", ""))

        if dtype == DiagramType.PROCESS_FLOW:
            spec.process_flow = ProcessFlowSpec(
                direction=data.get("direction", "horizontal"),
                nodes=data.get("nodes", []),
                connections=data.get("connections", []),
            )
        elif dtype == DiagramType.ARCHITECTURE:
            spec.architecture = ArchitectureSpec(
                variant=data.get("variant", "layers"),
                layers=data.get("layers", []),
                cross_cutting=data.get("cross_cutting", []),
                root=data.get("root", {}),
            )
        elif dtype == DiagramType.RELATIONSHIP:
            spec.relationship = RelationshipSpec(
                variant=data.get("variant", "causal"),
                nodes=data.get("nodes", []),
                edges=data.get("edges", []),
            )
        elif dtype == DiagramType.FRAMEWORK:
            spec.framework = FrameworkSpec(
                variant=data.get("variant", "matrix_2x2"),
                x_axis=data.get("x_axis", {}),
                y_axis=data.get("y_axis", {}),
                quadrants=data.get("quadrants", []),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                opportunities=data.get("opportunities", []),
                threats=data.get("threats", []),
                pyramid_levels=data.get("pyramid_levels", []),
                funnel_stages=data.get("funnel_stages", []),
                circles=data.get("circles", []),
                intersection=data.get("intersection", []),
            )
        return spec

    def to_dict(self) -> dict:
        result = {"diagram_type": self.diagram_type.value, "title": self.title}
        if self.process_flow:
            result.update({
                "direction": self.process_flow.direction,
                "nodes": self.process_flow.nodes,
                "connections": self.process_flow.connections,
            })
        elif self.architecture:
            result.update({
                "variant": self.architecture.variant,
                "layers": self.architecture.layers,
                "cross_cutting": self.architecture.cross_cutting,
                "root": self.architecture.root,
            })
        elif self.relationship:
            result.update({
                "variant": self.relationship.variant,
                "nodes": self.relationship.nodes,
                "edges": self.relationship.edges,
            })
        elif self.framework:
            result.update({
                "variant": self.framework.variant,
                "x_axis": self.framework.x_axis,
                "y_axis": self.framework.y_axis,
                "quadrants": self.framework.quadrants,
                "strengths": self.framework.strengths,
                "weaknesses": self.framework.weaknesses,
                "opportunities": self.framework.opportunities,
                "threats": self.framework.threats,
                "pyramid_levels": self.framework.pyramid_levels,
                "funnel_stages": self.framework.funnel_stages,
                "circles": self.framework.circles,
                "intersection": self.framework.intersection,
            })
        return result


# ============================================================
# 内容填充层（content阶段）每页输出
# ============================================================

@dataclass
class SlideContent:
    """content阶段为每页生成的详细内容"""
    page_number: int
    slide_type: str                     # 从大纲继承
    takeaway_message: str               # 从大纲继承，可能微调措辞

    text_blocks: list[TextBlock] = field(default_factory=list)
    data_references: list[dict] = field(default_factory=list)
    # [{"source": "Sheet1: 季度收入", "key_values": {"Q1": "3.2亿", ...}}]
    chart_suggestion: Optional[ChartSuggestion] = None
    diagram_spec: Optional[ContentDiagramSpec] = None
    visual_block: Optional[VisualBlock] = None   # 可视化块提示
    primary_visual: str = ""            # PrimaryVisualType值
    source_note: str = ""               # 数据来源脚注

    # 状态
    warnings: list[str] = field(default_factory=list)  # 质量校验警告
    is_failed: bool = False             # 生成失败标记
    error_message: str = ""             # 失败原因

    def to_dict(self) -> dict:
        result = {
            "page_number": self.page_number,
            "slide_type": self.slide_type,
            "takeaway_message": self.takeaway_message,
            "text_blocks": [
                {"block_id": b.block_id, "content": b.content,
                 "level": b.level, "is_bold": b.is_bold}
                for b in self.text_blocks
            ],
            "data_references": self.data_references,
            "source_note": self.source_note,
            "primary_visual": self.primary_visual,
            "warnings": self.warnings,
            "is_failed": self.is_failed,
            "error_message": self.error_message,
        }
        if self.chart_suggestion:
            result["chart_suggestion"] = {
                "chart_type": self.chart_suggestion.chart_type,
                "data_feature": self.chart_suggestion.data_feature,
                "title": self.chart_suggestion.title,
                "categories": self.chart_suggestion.categories,
                "series": self.chart_suggestion.series,
                "so_what": self.chart_suggestion.so_what,
            }
        if self.diagram_spec:
            result["diagram_spec"] = self.diagram_spec.to_dict()
        if self.visual_block:
            result["visual_block"] = self.visual_block.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> SlideContent:
        content = cls(
            page_number=data["page_number"],
            slide_type=data["slide_type"],
            takeaway_message=data["takeaway_message"],
            text_blocks=[
                TextBlock(block_id=b.get("block_id", f"txt_{uuid4().hex[:8]}"),
                          content=b["content"], level=b.get("level", 0),
                          is_bold=b.get("is_bold", False))
                for b in data.get("text_blocks", [])
            ],
            data_references=data.get("data_references", []),
            source_note=data.get("source_note", ""),
            primary_visual=data.get("primary_visual", ""),
            warnings=data.get("warnings", []),
            is_failed=data.get("is_failed", False),
            error_message=data.get("error_message", ""),
        )
        if "chart_suggestion" in data and data["chart_suggestion"]:
            cs = data["chart_suggestion"]
            content.chart_suggestion = ChartSuggestion(
                chart_type=cs.get("chart_type", "column"),
                data_feature=cs.get("data_feature", ""),
                title=cs.get("title", ""),
                categories=cs.get("categories", []),
                series=cs.get("series", []),
                so_what=cs.get("so_what", ""),
            )
        if "diagram_spec" in data and data["diagram_spec"]:
            content.diagram_spec = ContentDiagramSpec.from_dict(data["diagram_spec"])
        if "visual_block" in data and data["visual_block"]:
            content.visual_block = VisualBlock.from_dict(data["visual_block"])
        return content


# ============================================================
# 补充数据
# ============================================================

@dataclass
class SupplementalData:
    """用户补充的数据"""
    stage: str                          # "outline" or "content"
    page_number: Optional[int] = None   # None=全局, 数字=特定页
    text_data: str = ""
    file_path: str = ""                 # 上传文件路径


@dataclass
class ContentResult:
    """content阶段完整输出"""
    slides: list[SlideContent] = field(default_factory=list)
    total_pages: int = 0
    failed_pages: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_pages": self.total_pages,
            "failed_pages": self.failed_pages,
            "slides": [s.to_dict() for s in self.slides],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ContentResult:
        return cls(
            total_pages=data.get("total_pages", 0),
            failed_pages=data.get("failed_pages", []),
            slides=[SlideContent.from_dict(s) for s in data.get("slides", [])],
        )


# ============================================================
# ArgumentTree 模型（PlanAgent 输出）
# ============================================================

@dataclass
class SCQA:
    """金字塔原理中的情境-冲突-问题-答案结构"""
    situation: str = ""     # 现状背景
    complication: str = ""  # 挑战/冲突
    question: str = ""      # 核心疑问
    answer: str = ""        # 顶层结论 = root.claim

    def to_dict(self) -> dict:
        return {
            "situation": self.situation,
            "complication": self.complication,
            "question": self.question,
            "answer": self.answer,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SCQA":
        return cls(
            situation=d.get("situation", ""),
            complication=d.get("complication", ""),
            question=d.get("question", ""),
            answer=d.get("answer", ""),
        )


@dataclass
class Evidence:
    """论点的证据单元，来源可追溯到文档 chunk"""
    id: str = ""            # ev_{hash8}
    kind: str = "stat"      # stat / quote / case / chart / expert / doc
    content: str = ""       # 一句话事实陈述
    source_chunk_id: str = ""  # 对应 analyze_agent 生成的 chunk.id

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind,
                "content": self.content, "source_chunk_id": self.source_chunk_id}


@dataclass
class ClaimNode:
    """论证树中的一个节点（论点）"""
    id: str = ""                    # cl_{hash8}
    claim: str = ""                 # action title，完整句子，含动词
    question_answered: str = ""     # 回答父节点的哪个 why/how
    logic_type: str = "root"        # root / deductive / inductive
    slide_role: str = "key_message" # cover/opener/key_message/evidence/section/summary/cta
    evidences: list = field(default_factory=list)   # list[Evidence]
    children: list = field(default_factory=list)    # list[ClaimNode]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "claim": self.claim,
            "question_answered": self.question_answered,
            "logic_type": self.logic_type, "slide_role": self.slide_role,
            "evidences": [e.to_dict() if hasattr(e, "to_dict") else e for e in self.evidences],
            "children": [c.to_dict() if hasattr(c, "to_dict") else c for c in self.children],
        }


@dataclass
class ArgumentTree:
    """完整的金字塔论证结构"""
    scqa: SCQA = field(default_factory=SCQA)
    root: ClaimNode = field(default_factory=ClaimNode)
    narrative_arc: str = "scqa"     # scqa / scr / problem_solution / explanation

    def to_dict(self) -> dict:
        return {
            "scqa": self.scqa.to_dict(),
            "root": self.root.to_dict() if hasattr(self.root, "to_dict") else self.root,
            "narrative_arc": self.narrative_arc,
        }
