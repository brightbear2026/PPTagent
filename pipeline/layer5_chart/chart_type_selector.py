"""
图表类型选择器 - 基于数据特征的规则引擎
"""
import re
from models import SlideSpec, ChartType


class ChartTypeSelector:
    """根据slide内容和数据特征选择ChartType"""

    def select(self, slide: SlideSpec) -> ChartType:
        """选择图表类型"""
        text = self._collect_text(slide)
        arc = slide.narrave_arc if hasattr(slide, 'narrave_arc') else slide.narrative_arc

        # 趋势类
        if self._is_trend(text):
            return ChartType.LINE

        # 占比/构成类
        if self._is_composition(text):
            return ChartType.PIE

        # 对比类
        if arc.value in ("comparison", "evidence", "analysis") or self._is_compare(text):
            return ChartType.COLUMN

        # 默认柱形图
        return ChartType.COLUMN

    def _collect_text(self, slide: SlideSpec) -> str:
        parts = [slide.takeaway_message]
        for b in slide.text_blocks:
            parts.append(b.content)
        return " ".join(parts)

    def _is_trend(self, text: str) -> bool:
        keywords = ["趋势", "增长", "下降", "变化", "走势", "同比", "环比",
                    "上升", "降低", "逐年", "月度", "季度", "年度"]
        return any(k in text for k in keywords)

    def _is_composition(self, text: str) -> bool:
        keywords = ["占比", "比例", "构成", "分布", "份额", "百分比"]
        return any(k in text for k in keywords)

    def _is_compare(self, text: str) -> bool:
        keywords = ["对比", "比较", "vs", "差异", "排名", "最高", "最低", "前三"]
        return any(k in text for k in keywords)
