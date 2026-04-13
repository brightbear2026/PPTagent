"""
ContentPattern匹配引擎 - 基于规则的决策树
"""
import re
from models import SlideSpec, SlideType, NarrativeRole, ContentPattern, VisualBlockType


class PatternMatcher:
    """根据slide内容特征选择最合适的ContentPattern"""

    _VISUAL_BLOCK_TO_PATTERN = {
        VisualBlockType.KPI_CARDS: ContentPattern.KPI_HIGHLIGHT,
        VisualBlockType.STEP_CARDS: ContentPattern.STEP_FLOW,
        VisualBlockType.ICON_TEXT_GRID: ContentPattern.ICON_GRID,
        VisualBlockType.STAT_HIGHLIGHT: ContentPattern.STAT_CALLOUT,
        VisualBlockType.COMPARISON_COLUMNS: ContentPattern.TWO_COLUMN,
        VisualBlockType.CALLOUT_BOX: ContentPattern.STAT_CALLOUT,
    }

    # 时间线关键词（必须有明确的多时间点序列，非一般增长描述）
    _TIME_KEYWORDS = re.compile(
        r"\d{4}年.*\d{4}年|Q[1-4].*Q[1-4]|"
        r"第[一二三四五]阶段|阶段[一二三四五]|"
        r"\d{4}[/\-]\d{1,2}.*\d{4}[/\-]\d{1,2}|"
        r"H[12].*H[12]|时间线|路线图|里程碑"
    )

    # 对比相关关键词
    _COMPARE_KEYWORDS = re.compile(
        r"对比|比较|vs|versus|相较|区别|差异|优劣势|不同|各有|"
        r"A/B|方案[一二三四五]|选项[一二三四五]"
    )

    # 流程相关关键词
    _PROCESS_KEYWORDS = re.compile(
        r"流程|步骤|环节|阶段|pipeline|第一步|第二步|第三步|"
        r"首先|然后|接着|最后|上游|下游|端到端"
    )

    def match(self, slide: SlideSpec) -> ContentPattern:
        """主匹配方法：primary_visual 最高优先级 → 决策树 fallback"""
        st = slide.slide_type

        # ── 最高优先级：primary_visual 驱动 ──
        pv = getattr(slide, 'primary_visual', '')
        if pv == 'chart':
            num_blocks = self._count_top_level_blocks(slide)
            if num_blocks <= 2:
                return ContentPattern.DATA_DASHBOARD
            return ContentPattern.LEFT_CHART_RIGHT_TEXT
        if pv == 'diagram':
            return ContentPattern.PROCESS_FLOW
        if pv == 'visual_block':
            vb = getattr(slide, 'visual_block', None)
            if vb and vb.block_type != VisualBlockType.BULLET_LIST:
                mapped = self._VISUAL_BLOCK_TO_PATTERN.get(vb.block_type)
                if mapped:
                    return mapped
            return ContentPattern.ARGUMENT_EVIDENCE
        if pv == 'text_only':
            # 特殊 slide_type 直接映射
            if st == SlideType.TITLE:
                return ContentPattern.TITLE_ONLY
            if st == SlideType.AGENDA:
                return ContentPattern.AGENDA_LIST
            if st == SlideType.SECTION_DIVIDER:
                return ContentPattern.TITLE_ONLY
            if st == SlideType.SUMMARY:
                return ContentPattern.ARGUMENT_EVIDENCE
            return ContentPattern.ARGUMENT_EVIDENCE

        # ── Fallback：旧数据无 primary_visual，走原有决策树 ──

        # 零级守护：如果 slide 已有 charts，强制使用图表布局
        if slide.charts:
            num_blocks = self._count_top_level_blocks(slide)
            if num_blocks <= 2:
                return ContentPattern.DATA_DASHBOARD
            return ContentPattern.LEFT_CHART_RIGHT_TEXT

        # 如果 slide 已有 diagrams，强制使用流程布局
        if slide.diagrams:
            return ContentPattern.PROCESS_FLOW

        # visual_block 驱动
        vb = getattr(slide, 'visual_block', None)
        if vb and vb.block_type != VisualBlockType.BULLET_LIST:
            mapped = self._VISUAL_BLOCK_TO_PATTERN.get(vb.block_type)
            if mapped:
                return mapped

        # 一级过滤：特殊slide_type
        if st == SlideType.TITLE:
            return ContentPattern.TITLE_ONLY
        if st == SlideType.AGENDA:
            return ContentPattern.AGENDA_LIST
        if st == SlideType.SECTION_DIVIDER:
            return ContentPattern.TITLE_ONLY
        if st == SlideType.SUMMARY:
            return ContentPattern.ARGUMENT_EVIDENCE

        # 二级决策：基于narrative_arc和内容特征
        arc = slide.narrative_arc
        text = self._collect_text(slide)
        has_data = bool(slide.data_references) or self._has_numbers(text)
        num_blocks = self._count_top_level_blocks(slide)

        # 对比类
        if arc == NarrativeRole.COMPARISON or st == SlideType.COMPARISON:
            return ContentPattern.TWO_COLUMN

        # 流程类
        if self._PROCESS_KEYWORDS.search(text) and num_blocks >= 3:
            return ContentPattern.PROCESS_FLOW

        # 时间线类
        if self._TIME_KEYWORDS.search(text) and has_data and num_blocks >= 3:
            return ContentPattern.TIMELINE_HORIZONTAL

        # 矩阵类
        if st == SlideType.MATRIX or "象限" in text or "2x2" in text.lower():
            return ContentPattern.MATRIX_2X2

        # 有数据 + 少文本 → 数据仪表盘
        if has_data and num_blocks <= 2:
            return ContentPattern.DATA_DASHBOARD

        # 有数据 + 多文本 → 图文混合
        if has_data and num_blocks > 2:
            return ContentPattern.LEFT_CHART_RIGHT_TEXT

        # 三栏并列
        if num_blocks >= 6:
            return ContentPattern.THREE_COLUMN

        # 默认：论点+证据
        return ContentPattern.ARGUMENT_EVIDENCE

    def _collect_text(self, slide: SlideSpec) -> str:
        """收集slide中所有文本"""
        parts = [slide.takeaway_message]
        for block in slide.text_blocks:
            parts.append(block.content)
        for elem in slide.supporting_elements:
            parts.append(elem.content)
        return " ".join(parts)

    def _has_numbers(self, text: str) -> bool:
        """检测文本中是否包含数值数据"""
        return bool(re.search(r"\d+\.?\d*%|\d+\.?\d*[亿万百千]", text))

    def _count_top_level_blocks(self, slide: SlideSpec) -> int:
        """计算顶层文本块数量"""
        return sum(1 for b in slide.text_blocks if b.level == 0)
