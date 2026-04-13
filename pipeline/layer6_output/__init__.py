"""
Layer 6: Output Builder
将SlideSpec转换为最终.pptx文件

核心职责：
- 计算精确的布局坐标
- 使用python-pptx构建PPT
- 应用视觉主题
- 处理文本、图表、拓扑图
"""

from .ppt_builder import PPTBuilder
from .layout_engine import LayoutEngine

__all__ = ["PPTBuilder", "LayoutEngine"]
