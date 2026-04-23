"""
Chart Skills 包

导入此包即自动注册所有 Chart Skills 到 SkillRegistry。
"""

from pipeline.skills import SkillRegistry
from pipeline.skills.charts.chart_skills import (
    ColumnChartSkill,
    BarChartSkill,
    LineChartSkill,
    PieChartSkill,
    AreaChartSkill,
    ScatterChartSkill,
    WaterfallChartSkill,
    ComboChartSkill,
)

_registry = SkillRegistry.get()
_registry.register(ColumnChartSkill())
_registry.register(BarChartSkill())
_registry.register(LineChartSkill())
_registry.register(PieChartSkill())
_registry.register(AreaChartSkill())
_registry.register(ScatterChartSkill())
_registry.register(WaterfallChartSkill())
_registry.register(ComboChartSkill())
