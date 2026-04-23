"""
布局验证引擎 — 碰撞检测 + 溢出处理 + 自动修正

在 LayoutEngine 计算坐标之后、ppt_builder 创建 shape 之前运行。
检测问题并修正 LayoutCoordinates，防止元素重叠和溢出。

设计原则（参考 Beautiful.ai）：
- 约束设计空间本身就是防止坏设计的最有效方法
- 预防性验证 > 事后修补
- 级联策略：缩小字号 → 截短文本 → 切换模板 → 拆分幻灯片
"""

from dataclasses import dataclass, field
from typing import Optional

from models.slide_spec import Rect, SlideSpec, LayoutCoordinates


# ============================================================
# 数据结构
# ============================================================

@dataclass
class LayoutWarning:
    """布局警告"""
    severity: str          # "error" | "warning" | "info"
    category: str          # "collision" | "margin" | "overflow" | "font_size" | "fill_ratio"
    message: str
    rect_a: Optional[Rect] = None
    rect_b: Optional[Rect] = None


@dataclass
class VerificationReport:
    """验证报告"""
    warnings: list[LayoutWarning] = field(default_factory=list)
    has_errors: bool = False

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def add(self, severity: str, category: str, message: str,
            rect_a: Rect = None, rect_b: Rect = None):
        self.warnings.append(LayoutWarning(severity, category, message, rect_a, rect_b))
        if severity == "error":
            self.has_errors = True


# ============================================================
# 常量
# ============================================================

# 标准幻灯片尺寸 (EMU)
SLIDE_WIDTH = 12192000   # 13.333 inches
SLIDE_HEIGHT = 6858000   # 7.5 inches

# 最小边距 (EMU)
MIN_MARGIN = 137160      # 0.15 inch

# 元素间最小间距 (EMU)
MIN_ELEMENT_GAP = 91440  # 0.10 inch

# 填充率范围
MIN_FILL_RATIO = 0.10    # 10% — 低于此值页面太空
MAX_FILL_RATIO = 0.65    # 65% — 高于此值页面太满

# 字号下限 (pt)
MIN_TITLE_FONT_PT = 14
MIN_BODY_FONT_PT = 8

# IoU 阈值
COLLISION_IOU_THRESHOLD = 0.1    # IoU > 10% 视为碰撞
OVERLAP_IOU_THRESHOLD = 0.02     # IoU > 2% 视为接触


class LayoutVerifier:
    """
    布局验证引擎。

    在 LayoutEngine.calculate_layout() 之后运行，
    检测并修正布局问题，确保元素不重叠、不溢出、间距合理。
    """

    def __init__(self):
        self.slide_width = SLIDE_WIDTH
        self.slide_height = SLIDE_HEIGHT
        self.min_margin = MIN_MARGIN

    def verify(
        self,
        spec: SlideSpec,
        layout: LayoutCoordinates,
        theme=None,
    ) -> VerificationReport:
        """
        验证单页布局。

        Args:
            spec: 页面规格
            layout: 计算好的坐标
            theme: 视觉主题（用于字号检查）

        Returns:
            VerificationReport 包含所有警告和错误
        """
        report = VerificationReport()

        # 收集所有非空 Rect
        all_rects = self._collect_rects(layout)

        if not all_rects:
            report.add("warning", "fill_ratio", "页面无任何布局区域")
            return report

        # 1. AABB碰撞检测
        self._check_collisions(all_rects, report)

        # 2. 边距检查
        self._check_margins(all_rects, report)

        # 3. 内容vs区域匹配
        self._check_content_fit(spec, layout, report)

        # 4. 填充率检查
        self._check_fill_ratio(all_rects, report)

        return report

    def auto_fix(
        self,
        spec: SlideSpec,
        layout: LayoutCoordinates,
        report: VerificationReport,
    ) -> LayoutCoordinates:
        """
        自动修正布局问题。

        级联策略：
        1. 间距修正 — 推开重叠的Rect
        2. 边距修正 — 将超出边界的Rect拉回
        3. 区域裁剪 — 将过大的Rect缩小

        返回修正后的 LayoutCoordinates。
        """
        if not report.has_warnings:
            return layout

        all_rects = self._collect_rects(layout)
        if not all_rects:
            return layout

        # 第一步：间距修正（推开重叠Rect）
        self._fix_spacing(all_rects)

        # 第二步：边距修正（拉回超出边界的Rect）
        self._fix_margins(all_rects)

        # 第三步：将修正后的Rect写回LayoutCoordinates
        self._write_back_rects(layout, all_rects)

        return layout

    def verify_and_fix(
        self,
        spec: SlideSpec,
        layout: LayoutCoordinates,
        theme=None,
    ) -> tuple[LayoutCoordinates, VerificationReport]:
        """
        验证并自动修正（一站式调用）。
        """
        report = self.verify(spec, layout, theme)
        if report.has_errors:
            layout = self.auto_fix(spec, layout, report)
        return layout, report

    # ================================================================
    # Rect 收集
    # ================================================================

    @staticmethod
    def _collect_rects(layout: LayoutCoordinates) -> list[tuple[str, Rect]]:
        """收集所有非空 Rect，附带标签"""
        rects = []
        for attr in ('title_area', 'takeaway_area', 'footnote_area',
                      'logo_area', 'source_area'):
            r = getattr(layout, attr, None)
            if r and isinstance(r, Rect) and r.width > 0 and r.height > 0:
                rects.append((attr, r))

        for list_attr in ('body_areas', 'chart_areas', 'diagram_areas',
                          'picture_areas', 'visual_block_areas'):
            for i, r in enumerate(getattr(layout, list_attr, [])):
                if isinstance(r, Rect) and r.width > 0 and r.height > 0:
                    rects.append((f"{list_attr}[{i}]", r))

        return rects

    @staticmethod
    def _write_back_rects(layout: LayoutCoordinates, rects: list[tuple[str, Rect]]):
        """将修正后的Rect写回LayoutCoordinates"""
        # 按属性分组
        single_attrs = {}
        list_attrs = {}

        for label, rect in rects:
            if '[' in label:
                attr = label.split('[')[0]
                idx = int(label.split('[')[1].rstrip(']'))
                if attr not in list_attrs:
                    list_attrs[attr] = {}
                list_attrs[attr][idx] = rect
            else:
                single_attrs[label] = rect

        # 写回单值属性
        for attr, rect in single_attrs.items():
            if hasattr(layout, attr):
                setattr(layout, attr, rect)

        # 写回列表属性
        for attr, idx_map in list_attrs.items():
            old_list = getattr(layout, attr, [])
            for idx, rect in idx_map.items():
                if idx < len(old_list):
                    old_list[idx] = rect

    # ================================================================
    # 检测逻辑
    # ================================================================

    @staticmethod
    def _iou(a: Rect, b: Rect) -> float:
        """计算两个Rect的交并比 (Intersection over Union)"""
        # 交集
        x_overlap = max(0, min(a.left + a.width, b.left + b.width) - max(a.left, b.left))
        y_overlap = max(0, min(a.top + a.height, b.top + b.height) - max(a.top, b.top))
        intersection = x_overlap * y_overlap

        if intersection == 0:
            return 0.0

        area_a = a.width * a.height
        area_b = b.width * b.height
        union = area_a + area_b - intersection

        return intersection / max(union, 1)

    def _check_collisions(self, rects: list[tuple[str, Rect]], report: VerificationReport):
        """AABB碰撞检测：所有Rect两两检查"""
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                label_a, rect_a = rects[i]
                label_b, rect_b = rects[j]

                iou = self._iou(rect_a, rect_b)
                if iou > COLLISION_IOU_THRESHOLD:
                    severity = "error" if iou > 0.3 else "warning"
                    report.add(
                        severity, "collision",
                        f"{label_a} 与 {label_b} 重叠 (IoU={iou:.1%})",
                        rect_a, rect_b,
                    )

    def _check_margins(self, rects: list[tuple[str, Rect]], report: VerificationReport):
        """边距检查：所有Rect是否在内容区域内"""
        for label, rect in rects:
            # 左边距
            if rect.left < self.min_margin:
                report.add("error", "margin",
                           f"{label} 左侧超出边距 (left={rect.left}, 最小={self.min_margin})")
            # 上边距
            if rect.top < self.min_margin:
                report.add("error", "margin",
                           f"{label} 顶部超出边距 (top={rect.top}, 最小={self.min_margin})")
            # 右边距
            right = rect.left + rect.width
            if right > self.slide_width - self.min_margin:
                report.add("warning", "margin",
                           f"{label} 右侧超出边距 (right={right}, 最大={self.slide_width - self.min_margin})")
            # 下边距
            bottom = rect.top + rect.height
            if bottom > self.slide_height - self.min_margin:
                report.add("warning", "margin",
                           f"{label} 底部超出边距 (bottom={bottom}, 最大={self.slide_height - self.min_margin})")

    def _check_content_fit(self, spec: SlideSpec, layout: LayoutCoordinates,
                           report: VerificationReport):
        """检查内容与区域的匹配度"""
        # 有图表但无chart_areas
        if spec.charts and not layout.chart_areas:
            report.add("warning", "overflow",
                       f"有{len(spec.charts)}个图表但无chart_area")

        # 有图表但无图区域
        if spec.diagrams and not layout.diagram_areas:
            report.add("warning", "overflow",
                       f"有{len(spec.diagrams)}个图表但无diagram_area")

        # 图表数与区域数不匹配
        if spec.charts and layout.chart_areas:
            if len(spec.charts) > len(layout.chart_areas):
                report.add("warning", "overflow",
                           f"图表数({len(spec.charts)}) > chart_area数({len(layout.chart_areas)})")

        # 文本块数与区域数严重不匹配
        text_blocks = getattr(spec, 'text_blocks', []) or []
        if text_blocks and layout.body_areas:
            # 每个body_area最多能容纳的文本块数估算
            total_body_height = sum(r.height for r in layout.body_areas)
            if total_body_height < 200000:  # 约0.22 inch，太小
                report.add("warning", "overflow",
                           f"body_area总高度太小({total_body_height} EMU)")

    def _check_fill_ratio(self, rects: list[tuple[str, Rect]], report: VerificationReport):
        """填充率检查"""
        total_area = 0
        for _, rect in rects:
            total_area += rect.width * rect.height

        slide_area = self.slide_width * self.slide_height
        fill_ratio = total_area / max(slide_area, 1)

        if fill_ratio < MIN_FILL_RATIO:
            report.add("info", "fill_ratio",
                       f"页面填充率过低 ({fill_ratio:.0%})")
        elif fill_ratio > MAX_FILL_RATIO:
            report.add("warning", "fill_ratio",
                       f"页面填充率过高 ({fill_ratio:.0%})")

    # ================================================================
    # 修正逻辑
    # ================================================================

    def _fix_spacing(self, rects: list[tuple[str, Rect]]):
        """间距修正：推开重叠的Rect"""
        # 按重要性排序：title > takeaway > body > chart > 其他
        priority = {
            'title_area': 0, 'takeaway_area': 1,
            'footnote_area': 5, 'source_area': 6, 'logo_area': 7,
        }

        def get_priority(label):
            base = label.split('[')[0]
            return priority.get(base, 3)  # 默认优先级3（body/chart等）

        sorted_rects = sorted(rects, key=lambda x: get_priority(x[0]))

        # 逐个推开重叠
        for i in range(len(sorted_rects)):
            _, rect_a = sorted_rects[i]
            for j in range(i + 1, len(sorted_rects)):
                _, rect_b = sorted_rects[j]

                iou = self._iou(rect_a, rect_b)
                if iou > OVERLAP_IOU_THRESHOLD:
                    # 将 rect_b 向下推
                    overlap_y = (rect_a.top + rect_a.height + MIN_ELEMENT_GAP) - rect_b.top
                    if overlap_y > 0:
                        rect_b.top += overlap_y

    def _fix_margins(self, rects: list[tuple[str, Rect]]):
        """边距修正：将超出边界的Rect拉回"""
        for _, rect in rects:
            # 左边距
            if rect.left < self.min_margin:
                rect.left = self.min_margin
            # 上边距
            if rect.top < self.min_margin:
                rect.top = self.min_margin
            # 右边距：如果超出，缩小宽度
            right = rect.left + rect.width
            max_right = self.slide_width - self.min_margin
            if right > max_right:
                rect.width = max_right - rect.left
            # 下边距：如果超出，缩小高度
            bottom = rect.top + rect.height
            max_bottom = self.slide_height - self.min_margin
            if bottom > max_bottom:
                rect.height = max_bottom - rect.top
