"""
Diagram Skills 包

导入此包即自动注册所有 Diagram Skills 到 SkillRegistry。
"""

from pipeline.skills import SkillRegistry
from pipeline.skills.diagrams.process_flow import ProcessFlowSkill
from pipeline.skills.diagrams.architecture import ArchitectureSkill
from pipeline.skills.diagrams.relationship import RelationshipSkill
from pipeline.skills.diagrams.framework import FrameworkSkill
from pipeline.skills.diagrams.tech_architecture import TechArchitectureSkill
from pipeline.skills.diagrams.component_topology import ComponentTopologySkill
from pipeline.skills.diagrams.data_flow import DataFlowSkill
from pipeline.skills.diagrams.tech_stack_matrix import TechStackMatrixSkill

_registry = SkillRegistry.get()
_registry.register(ProcessFlowSkill())
_registry.register(ArchitectureSkill())
_registry.register(RelationshipSkill())
_registry.register(FrameworkSkill())
_registry.register(TechArchitectureSkill())
_registry.register(ComponentTopologySkill())
_registry.register(DataFlowSkill())
_registry.register(TechStackMatrixSkill())
