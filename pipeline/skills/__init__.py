"""
Skill 注册中心

提供统一的 Skill 注册、查找、Prompt 汇总能力。
使用简单 dict 注册，无需复杂的置信度匹配。
"""

from typing import Optional
from pipeline.skills.base import RenderingSkill, SkillDescriptor


class SkillRegistry:
    """
    全局 Skill 注册表（单例模式）

    用法：
        registry = SkillRegistry.get()
        skill = registry.find("visual_block", "kpi_cards")
        prompt = registry.get_prompt_fragments("visual_block")
    """

    _instance: Optional["SkillRegistry"] = None

    def __init__(self):
        self._skills: dict[str, RenderingSkill] = {}  # skill_id -> skill
        self._type_index: dict[str, list[str]] = {}    # skill_type -> [skill_id, ...]

    @classmethod
    def get(cls) -> "SkillRegistry":
        """获取全局单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """重置注册表（测试用）"""
        cls._instance = None

    def register(self, skill: RenderingSkill):
        """注册一个 Skill"""
        desc = skill.descriptor()
        self._skills[desc.skill_id] = skill

        if desc.skill_type not in self._type_index:
            self._type_index[desc.skill_type] = []
        self._type_index[desc.skill_type].append(desc.skill_id)

    def find(self, skill_type: str, handles_type: str) -> Optional[RenderingSkill]:
        """
        按 skill_type + handles_type 查找 Skill

        Args:
            skill_type: "visual_block" | "chart" | "diagram"
            handles_type: 具体类型，如 "kpi_cards"、"bar"、"process_flow"
        """
        for skill_id in self._type_index.get(skill_type, []):
            skill = self._skills[skill_id]
            if handles_type in skill.descriptor().handles_types:
                return skill
        return None

    def all_of_type(self, skill_type: str) -> list[RenderingSkill]:
        """获取某类型的所有 Skill"""
        ids = self._type_index.get(skill_type, [])
        return [self._skills[sid] for sid in ids]

    def get_prompt_fragments(self, skill_type: str) -> str:
        """
        汇总某类型所有 Skill 的 Prompt 片段

        用于 content_filler 的 LLM Prompt 动态组装：
        只包含当前 batch 需要的类型，避免注意力分散。
        """
        skills = self.all_of_type(skill_type)
        fragments = []
        for skill in skills:
            frag = skill.prompt_fragment()
            if frag:
                fragments.append(frag)
        return "\n\n".join(fragments)

    def list_registered(self) -> list[dict]:
        """列出所有已注册的 Skill（调试用）"""
        result = []
        for sid, skill in self._skills.items():
            desc = skill.descriptor()
            result.append({
                "skill_id": desc.skill_id,
                "skill_type": desc.skill_type,
                "handles_types": desc.handles_types,
            })
        return result
