"""
Layer 3: Structure Planner
基于Narrative生成SlideSpec列表，每页有明确的takeaway和narrative角色

核心职责：
- 将Narrative拆分为单个页面
- 为每页确定核心论点（takeaway_message）
- 分配叙事角色（narrative_arc）
- 生成第1个用户确认点
"""

from .structure_planner import StructurePlanner

__all__ = ["StructurePlanner"]
