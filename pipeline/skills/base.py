"""
Skill 基础类定义

Skill = Prompt 指导 + 设计参数 + 渲染规则（三位一体的设计知识封装单元）

每种视觉元素类型（visual_block / chart / diagram）都实现 RenderingSkill 接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SkillDescriptor:
    """Skill 元信息"""
    skill_id: str               # 唯一标识，如 "vb_kpi_cards"
    skill_type: str             # "visual_block" | "chart" | "diagram"
    handles_types: list[str]    # 该 Skill 处理的具体类型，如 ["kpi_cards"]
    content_pattern: Optional[str] = None  # 对应的 ContentPattern（可选）


class RenderingSkill(ABC):
    """
    渲染 Skill 抽象基类

    子类必须实现三个方法：
    - prompt_fragment(): 返回该类型的 Prompt 指导文本（注入到 content_filler 的 LLM 调用中）
    - design_tokens(): 返回设计参数 dict（颜色、字号、间距等，跟随主题）
    - render(): 执行实际渲染（python-pptx 操作）
    """

    @abstractmethod
    def descriptor(self) -> SkillDescriptor:
        """返回 Skill 元信息"""

    @abstractmethod
    def prompt_fragment(self) -> str:
        """
        返回该类型的 Prompt 指导文本。

        内容应包含：设计理念 + 字段说明 + 质量要求。
        这些文本会被注入到 content_filler 的 LLM Prompt 中，
        指导 LLM 生成更高质量的内容。
        """

    @abstractmethod
    def design_tokens(self) -> dict:
        """
        返回设计参数 dict。

        参数从 theme 中读取，不硬编码。典型字段：
        - bg_color_key: str — 从 theme.colors 读取的 key
        - font_size_range: (min, max) — 字号自适应范围
        - max_items: int — 最大元素数量
        - gap_inches: float — 元素间距
        """

    @abstractmethod
    def render(self, slide, data, rect, theme) -> bool:
        """
        执行渲染。

        Args:
            slide: python-pptx Slide 对象
            data: 渲染数据（VisualBlock / ChartSpec / DiagramSpec）
            rect: Rect 渲染区域
            theme: VisualTheme 主题配置

        Returns:
            True 渲染成功，False 渲染失败（将 fallback 到默认文本模式）
        """
