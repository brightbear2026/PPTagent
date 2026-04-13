"""
Layer 2: Content Analysis
内容分析层 - 两步走策略

核心职责：
1. 信息提取：将RawContent分解为事实/数据/观点/结论
2. 论证结构编排：将元素组织成有逻辑的叙事线

输出：Narrative对象（完整的叙事结构）
"""

from .content_extractor import ContentExtractor
from .narrative_architect import NarrativeArchitect

__all__ = ["ContentExtractor", "NarrativeArchitect"]
