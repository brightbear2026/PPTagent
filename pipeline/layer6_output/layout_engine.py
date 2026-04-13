"""
布局引擎：计算PPT页面元素的精确坐标
支持基于ContentPattern的多布局模板，优先从模板库加载
"""
from typing import Optional
from models import SlideSpec, LayoutCoordinates, Rect, ContentPattern


# 槽位名到LayoutCoordinates字段的映射
SLOT_TO_FIELD = {
    "title": "title_area",
    "subtitle": "title_area",
    "takeaway": "takeaway_area",
    "body": "_body",
    "evidence": "_body",
    "left": "_body",
    "right": "_body",
    "col1": "_body",
    "col2": "_body",
    "col3": "_body",
    "top_left": "_body",
    "top_right": "_body",
    "bottom_left": "_body",
    "bottom_right": "_body",
    "block1": "_visual_block",
    "block2": "_visual_block",
    "block3": "_visual_block",
    "block4": "_visual_block",
    "block5": "_visual_block",
    "block6": "_visual_block",
    "left_header": "_body",
    "right_header": "_body",
    "left_accent": "_body",
    "quote": "_body",
    "attribution": "_body",
    "image": "_body",
    "chart": "_chart",
    "diagram": "_diagram",
    "picture": "_picture",
    "image": "_picture",
    "kpi1": "_body",
    "kpi2": "_body",
    "kpi3": "_body",
    "kpi4": "_body",
    "footnote": "footnote_area",
    "logo": "logo_area",
    "source": "source_area",
}


class LayoutEngine:
    """
    根据内容密度和布局模板计算每个元素的精确位置
    使用参数化微调，不使用约束求解器
    """

    def __init__(self):
        # 标准PPT尺寸 (16:9): 13.333 x 7.5 英寸 = 12192000 x 6858000 EMUs
        self.slide_width = 12192000   # 13.333 inches (16:9比例)
        self.slide_height = 6858000   # 7.5 inches

        # 标准边距
        self.margin_top = 457200     # 0.5 inch
        self.margin_bottom = 457200  # 0.5 inch
        self.margin_left = 457200    # 0.5 inch
        self.margin_right = 457200   # 0.5 inch

        # 内容区域
        self.content_width = self.slide_width - self.margin_left - self.margin_right
        self.content_height = self.slide_height - self.margin_top - self.margin_bottom

        # 模板库（懒加载）
        self._skeleton_registry = None

    def _get_registry(self):
        """懒加载模板注册表"""
        if self._skeleton_registry is None:
            try:
                from templates.skeleton_registry import LayoutSkeletonRegistry
                self._skeleton_registry = LayoutSkeletonRegistry()
            except Exception:
                self._skeleton_registry = False  # 标记为不可用
        return self._skeleton_registry if self._skeleton_registry is not False else None

    def calculate_layout(self, slide: SlideSpec) -> LayoutCoordinates:
        """计算一页的所有元素坐标"""
        # 优先从模板库加载（如果layout_template_id有效）
        template_id = getattr(slide, "layout_template_id", None)
        if template_id:
            coords = self._layout_from_template(template_id)
            if coords:
                has_text = bool(slide.text_blocks)
                has_body = bool(coords.body_areas)
                has_chart_slot = bool(coords.chart_areas)
                has_diagram_slot = bool(coords.diagram_areas)
                # 模板有效条件：有文本时必须有 body 区域；有图表时必须有图表区域
                if has_body or (not has_text and (has_chart_slot or has_diagram_slot)):
                    self._ensure_picture_slot(coords, slide)
                    return coords

        # 回退：根据content_pattern选择布局
        if slide.content_pattern:
            coords = self._layout_by_pattern(slide)
        # 兼容旧逻辑：根据slide_type
        elif slide.slide_type.value == "title":
            coords = self._layout_title_page()
        elif slide.slide_type.value == "data":
            coords = self._layout_data_page(slide)
        else:
            coords = self._layout_content_page(slide)

        self._ensure_picture_slot(coords, slide)
        return coords

    def _ensure_picture_slot(self, coords: LayoutCoordinates, slide: SlideSpec):
        """
        若 slide 有 pictures 但 layout 未分配 picture_areas，则从第一个 body_area
        横切出右侧 38% 作为图片槽位，body_area 同步收窄。
        这样图文混排无需新增 pattern 即可生效。
        """
        pics = getattr(slide, "pictures", None) or []
        if not pics:
            return
        if coords.picture_areas:
            return
        if not coords.body_areas:
            return
        body = coords.body_areas[0]
        gap = 182880  # 0.2 inch
        pic_width = int(body.width * 0.38)
        new_body_width = body.width - pic_width - gap
        if new_body_width < 1828800:  # 小于 2 inch 就不切了
            return
        coords.body_areas[0] = Rect(
            left=body.left, top=body.top,
            width=new_body_width, height=body.height,
        )
        coords.picture_areas.append(Rect(
            left=body.left + new_body_width + gap,
            top=body.top,
            width=pic_width,
            height=body.height,
        ))

    def _layout_from_template(self, template_id: str) -> Optional[LayoutCoordinates]:
        """从模板库加载布局"""
        registry = self._get_registry()
        if not registry:
            return None

        rects = registry.resolve_slots_to_rects(template_id)
        if not rects:
            return None

        coords = LayoutCoordinates()
        for slot_name, rect in rects.items():
            field = SLOT_TO_FIELD.get(slot_name)
            if not field:
                continue

            if field == "title_area":
                coords.title_area = rect
            elif field == "takeaway_area":
                coords.takeaway_area = rect
            elif field == "footnote_area":
                coords.footnote_area = rect
            elif field == "logo_area":
                coords.logo_area = rect
            elif field == "source_area":
                coords.source_area = rect
            elif field == "_body":
                coords.body_areas.append(rect)
            elif field == "_visual_block":
                coords.visual_block_areas.append(rect)
            elif field == "_chart":
                coords.chart_areas.append(rect)
            elif field == "_diagram":
                coords.diagram_areas.append(rect)
            elif field == "_picture":
                coords.picture_areas.append(rect)

        return coords

    def _layout_by_pattern(self, slide: SlideSpec) -> LayoutCoordinates:
        """根据ContentPattern选择对应的布局计算"""
        pattern = slide.content_pattern
        handlers = {
            ContentPattern.TITLE_ONLY: self._layout_title_page,
            ContentPattern.AGENDA_LIST: self._layout_agenda,
            ContentPattern.ARGUMENT_EVIDENCE: self._layout_content_page,
            ContentPattern.TWO_COLUMN: self._layout_two_column,
            ContentPattern.THREE_COLUMN: self._layout_three_column,
            ContentPattern.LEFT_CHART_RIGHT_TEXT: self._layout_chart_text_split,
            ContentPattern.LEFT_TEXT_RIGHT_CHART: self._layout_text_chart_split,
            ContentPattern.MATRIX_2X2: self._layout_matrix_2x2,
            ContentPattern.TIMELINE_HORIZONTAL: self._layout_timeline,
            ContentPattern.PROCESS_FLOW: self._layout_process_flow,
            ContentPattern.DATA_DASHBOARD: self._layout_dashboard,
            ContentPattern.FULL_TABLE: self._layout_content_page,
            ContentPattern.KPI_HIGHLIGHT: self._layout_visual_block_page,
            ContentPattern.STEP_FLOW: self._layout_visual_block_page,
            ContentPattern.ICON_GRID: self._layout_visual_block_page,
            ContentPattern.STAT_CALLOUT: self._layout_visual_block_page,
        }
        handler = handlers.get(pattern, self._layout_content_page)
        # TITLE_ONLY和AGENDA不需要slide参数
        if pattern in (ContentPattern.TITLE_ONLY, ContentPattern.AGENDA_LIST):
            return handler()
        return handler(slide)

    # ── 基础布局 ──

    def _layout_title_page(self) -> LayoutCoordinates:
        """标题页布局：居中，大字体"""
        coords = LayoutCoordinates()
        coords.title_area = Rect(
            left=self.margin_left,
            top=self.slide_height // 3,
            width=self.content_width,
            height=914400  # 1 inch
        )
        return coords

    def _layout_agenda(self) -> LayoutCoordinates:
        """议程页布局"""
        coords = LayoutCoordinates()
        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=457200
        )
        coords.body_areas.append(Rect(
            left=self.margin_left,
            top=self.margin_top + 548640,
            width=self.content_width,
            height=self.content_height - 548640
        ))
        return coords

    def _layout_content_page(self, slide: SlideSpec = None) -> LayoutCoordinates:
        """内容页布局：标题 + 正文 + 可选图表/概念图"""
        coords = LayoutCoordinates()

        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=457200
        )

        body_top = self.margin_top + 548640  # 标题下方0.1inch间距
        gap = 91440  # 0.1 inch

        # primary_visual 感知：visual_block 不需要 chart/diagram 区域
        pv = getattr(slide, 'primary_visual', '') if slide else ''

        has_charts = slide and slide.charts and pv != 'visual_block'
        has_diagrams = slide and getattr(slide, "diagrams", None) and pv != 'visual_block'
        has_visual = has_charts or has_diagrams

        if has_visual:
            text_height = self.content_height // 3
            visual_height = self.content_height * 2 // 3

            coords.body_areas.append(Rect(
                left=self.margin_left,
                top=body_top,
                width=self.content_width,
                height=text_height
            ))

            visual_top = body_top + text_height + gap

            if has_charts and has_diagrams:
                half = (visual_height - gap) // 2
                coords.chart_areas.append(Rect(
                    left=self.margin_left,
                    top=visual_top,
                    width=self.content_width,
                    height=half
                ))
                coords.diagram_areas.append(Rect(
                    left=self.margin_left,
                    top=visual_top + half + gap,
                    width=self.content_width,
                    height=half
                ))
            elif has_charts:
                coords.chart_areas.append(Rect(
                    left=self.margin_left,
                    top=visual_top,
                    width=self.content_width,
                    height=visual_height - gap
                ))
            else:
                coords.diagram_areas.append(Rect(
                    left=self.margin_left,
                    top=visual_top,
                    width=self.content_width,
                    height=visual_height - gap
                ))
        else:
            # 纯文本或 visual_block 页面：body 占满全高度
            coords.body_areas.append(Rect(
                left=self.margin_left,
                top=body_top,
                width=self.content_width,
                height=self.content_height - 457200 - gap
            ))

        coords.source_area = Rect(
            left=self.margin_left,
            top=self.slide_height - self.margin_bottom - 182880,
            width=self.content_width,
            height=182880
        )
        return coords

    def _layout_visual_block_page(self, slide: SlideSpec) -> LayoutCoordinates:
        """可视化块页面布局：尝试模板加载，fallback 到标题+body全高"""
        # 优先尝试模板加载（模板中 block1-6 会映射到 visual_block_areas）
        template_id = getattr(slide, "layout_template_id", None)
        if template_id:
            coords = self._layout_from_template(template_id)
            if coords and coords.visual_block_areas:
                return coords

        # Fallback：标题 + body 全高度（渲染器自行在 body 内分割）
        coords = LayoutCoordinates()
        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=457200
        )
        body_top = self.margin_top + 548640
        coords.body_areas.append(Rect(
            left=self.margin_left,
            top=body_top,
            width=self.content_width,
            height=self.content_height - 457200 - 91440
        ))
        coords.source_area = Rect(
            left=self.margin_left,
            top=self.slide_height - self.margin_bottom - 182880,
            width=self.content_width,
            height=182880
        )
        return coords

    def _layout_data_page(self, slide: SlideSpec) -> LayoutCoordinates:
        """数据页布局：强调图表"""
        coords = LayoutCoordinates()
        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=274320
        )
        if slide.charts:
            coords.chart_areas.append(Rect(
                left=self.margin_left,
                top=self.margin_top + 365760,
                width=self.content_width,
                height=self.content_height - 365760 - 182880
            ))
        coords.source_area = Rect(
            left=self.margin_left,
            top=self.slide_height - self.margin_bottom - 182880,
            width=self.content_width,
            height=182880
        )
        return coords

    # ── Pattern布局 ──

    def _layout_chart_text_split(self, slide: SlideSpec) -> LayoutCoordinates:
        """左图表右文字 (60/40分割)"""
        coords = LayoutCoordinates()
        chart_width = int(self.content_width * 0.58)
        text_width = self.content_width - chart_width - 182880  # 0.2inch间距

        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=457200
        )

        body_top = self.margin_top + 548640

        coords.chart_areas.append(Rect(
            left=self.margin_left,
            top=body_top,
            width=chart_width,
            height=self.content_height - 548640 - 182880
        ))
        coords.body_areas.append(Rect(
            left=self.margin_left + chart_width + 182880,
            top=body_top,
            width=text_width,
            height=self.content_height - 548640 - 182880
        ))

        coords.source_area = Rect(
            left=self.margin_left,
            top=self.slide_height - self.margin_bottom - 182880,
            width=self.content_width,
            height=182880
        )
        return coords

    def _layout_text_chart_split(self, slide: SlideSpec) -> LayoutCoordinates:
        """左文字右图表 (40/60分割)"""
        coords = LayoutCoordinates()
        text_width = int(self.content_width * 0.38)
        chart_width = self.content_width - text_width - 182880

        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=457200
        )

        body_top = self.margin_top + 548640

        coords.body_areas.append(Rect(
            left=self.margin_left,
            top=body_top,
            width=text_width,
            height=self.content_height - 548640 - 182880
        ))
        coords.chart_areas.append(Rect(
            left=self.margin_left + text_width + 182880,
            top=body_top,
            width=chart_width,
            height=self.content_height - 548640 - 182880
        ))

        coords.source_area = Rect(
            left=self.margin_left,
            top=self.slide_height - self.margin_bottom - 182880,
            width=self.content_width,
            height=182880
        )
        return coords

    def _layout_two_column(self, slide: SlideSpec) -> LayoutCoordinates:
        """双栏布局"""
        coords = LayoutCoordinates()
        col_width = (self.content_width - 182880) // 2

        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=457200
        )

        body_top = self.margin_top + 548640
        body_height = self.content_height - 548640 - 182880

        coords.body_areas.append(Rect(
            left=self.margin_left,
            top=body_top,
            width=col_width,
            height=body_height
        ))
        coords.body_areas.append(Rect(
            left=self.margin_left + col_width + 182880,
            top=body_top,
            width=col_width,
            height=body_height
        ))

        coords.source_area = Rect(
            left=self.margin_left,
            top=self.slide_height - self.margin_bottom - 182880,
            width=self.content_width,
            height=182880
        )
        return coords

    def _layout_three_column(self, slide: SlideSpec) -> LayoutCoordinates:
        """三栏布局"""
        coords = LayoutCoordinates()
        gap = 137160  # ~0.15inch
        col_width = (self.content_width - gap * 2) // 3

        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=457200
        )

        body_top = self.margin_top + 548640
        body_height = self.content_height - 548640 - 182880

        for i in range(3):
            coords.body_areas.append(Rect(
                left=self.margin_left + i * (col_width + gap),
                top=body_top,
                width=col_width,
                height=body_height
            ))

        coords.source_area = Rect(
            left=self.margin_left,
            top=self.slide_height - self.margin_bottom - 182880,
            width=self.content_width,
            height=182880
        )
        return coords

    def _layout_matrix_2x2(self, slide: SlideSpec) -> LayoutCoordinates:
        """四象限布局"""
        coords = LayoutCoordinates()
        gap = 137160
        col_width = (self.content_width - gap) // 2
        row_height = (self.content_height - 548640 - 182880 - gap) // 2

        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=457200
        )

        body_top = self.margin_top + 548640

        positions = [
            (0, 0), (col_width + gap, 0),
            (0, row_height + gap), (col_width + gap, row_height + gap),
        ]
        for dx, dy in positions:
            coords.body_areas.append(Rect(
                left=self.margin_left + dx,
                top=body_top + dy,
                width=col_width,
                height=row_height
            ))

        coords.source_area = Rect(
            left=self.margin_left,
            top=self.slide_height - self.margin_bottom - 182880,
            width=self.content_width,
            height=182880
        )
        return coords

    def _layout_timeline(self, slide: SlideSpec) -> LayoutCoordinates:
        """时间线布局：标题 + 水平时间轴"""
        coords = LayoutCoordinates()
        coords.title_area = Rect(
            left=self.margin_left,
            top=self.margin_top,
            width=self.content_width,
            height=457200
        )
        # 时间轴区域
        coords.diagram_areas.append(Rect(
            left=self.margin_left,
            top=self.margin_top + 548640,
            width=self.content_width,
            height=self.content_height - 548640 - 182880
        ))
        coords.source_area = Rect(
            left=self.margin_left,
            top=self.slide_height - self.margin_bottom - 182880,
            width=self.content_width,
            height=182880
        )
        return coords

    def _layout_process_flow(self, slide: SlideSpec) -> LayoutCoordinates:
        """流程图布局"""
        return self._layout_timeline(slide)

    def _layout_dashboard(self, slide: SlideSpec) -> LayoutCoordinates:
        """数据仪表盘：上文下图"""
        return self._layout_content_page(slide)
