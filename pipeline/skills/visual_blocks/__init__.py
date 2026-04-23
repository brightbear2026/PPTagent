"""
Visual Block Skills 包

导入此包即自动注册所有 VB Skills 到 SkillRegistry。
"""

from pipeline.skills import SkillRegistry
from pipeline.skills.visual_blocks.kpi_cards import KpiCardsSkill
from pipeline.skills.visual_blocks.step_cards import StepCardsSkill
from pipeline.skills.visual_blocks.stat_highlight import StatHighlightSkill
from pipeline.skills.visual_blocks.comparison_columns import ComparisonColumnsSkill
from pipeline.skills.visual_blocks.icon_text_grid import IconTextGridSkill
from pipeline.skills.visual_blocks.callout_box import CalloutBoxSkill

_registry = SkillRegistry.get()
_registry.register(KpiCardsSkill())
_registry.register(StepCardsSkill())
_registry.register(StatHighlightSkill())
_registry.register(ComparisonColumnsSkill())
_registry.register(IconTextGridSkill())
_registry.register(CalloutBoxSkill())
