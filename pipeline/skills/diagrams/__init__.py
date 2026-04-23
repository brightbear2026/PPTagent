"""
Diagram Skills 包

导入此包即自动注册所有 Diagram Skills 到 SkillRegistry。
"""

from pipeline.skills import SkillRegistry
from pipeline.skills.diagrams.process_flow import ProcessFlowSkill
from pipeline.skills.diagrams.architecture import ArchitectureSkill
from pipeline.skills.diagrams.relationship import RelationshipSkill
from pipeline.skills.diagrams.framework import FrameworkSkill

_registry = SkillRegistry.get()
_registry.register(ProcessFlowSkill())
_registry.register(ArchitectureSkill())
_registry.register(RelationshipSkill())
_registry.register(FrameworkSkill())
