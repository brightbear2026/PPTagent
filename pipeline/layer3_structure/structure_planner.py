"""
Layer 3: Structure Planner
基于Narrative生成SlideSpec列表

这是整个流水线最关键的一层，决定PPT的质量上限
每页必须有明确的takeaway_message和narrative_arc
"""

import sys
from pathlib import Path
from typing import List
from dataclasses import dataclass

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from models import (
    SlideSpec, Narrative, NarrativeSection,
    SlideType, NarrativeRole, TextBlock
)


class StructurePlanner:
    """
    结构规划器：将Narrative转化为SlideSpec列表

    关键原则：
    1. 每页一个明确的论点（takeaway_message）
    2. 所有元素服务于这个论点
    3. 叙事流畅，角色清晰
    """

    def __init__(self):
        pass

    def plan_slides(self, narrative: Narrative) -> List[SlideSpec]:
        """
        将Narrative转换为SlideSpec列表

        Args:
            narrative: 完整的叙事结构（Layer 2输出）

        Returns:
            List[SlideSpec]: 每个slide有明确的takeaway和narrative_arc
        """
        print(f"\n📋 开始规划结构：{narrative.title}")
        print(f"   共 {len(narrative.sections)} 个叙事段落")

        slides = []

        # 1. 标题页
        title_slide = self._create_title_slide(narrative)
        slides.append(title_slide)

        # 2. 目录页（如果段落超过3个）
        if len(narrative.sections) > 3:
            agenda_slide = self._create_agenda_slide(narrative)
            slides.append(agenda_slide)

        # 3. 内容页：为每个NarrativeSection生成slide
        for idx, section in enumerate(narrative.sections):
            slide = self._create_content_slide(section, idx + 1)
            slides.append(slide)

        # 4. 总结页
        summary_slide = self._create_summary_slide(narrative)
        slides.append(summary_slide)

        print(f"✅ 结构规划完成：共 {len(slides)} 页")
        return slides

    def _create_title_slide(self, narrative: Narrative) -> SlideSpec:
        """创建标题页"""
        return SlideSpec(
            slide_type=SlideType.TITLE,
            takeaway_message=narrative.title,
            narrative_arc=NarrativeRole.OPENING
        )

    def _create_agenda_slide(self, narrative: Narrative) -> SlideSpec:
        """创建目录页"""
        agenda_items = [
            TextBlock(content=f"{idx+1}. {section.core_argument}", level=0)
            for idx, section in enumerate(narrative.sections)
        ]

        return SlideSpec(
            slide_type=SlideType.AGENDA,
            takeaway_message="本次汇报内容",
            narrative_arc=NarrativeRole.CONTEXT,
            text_blocks=agenda_items
        )

    def _create_content_slide(self, section: NarrativeSection, slide_num: int) -> SlideSpec:
        """
        为单个NarrativeSection创建内容页

        关键：每个section的核心论点就是这一页的takeaway
        """
        # 确定slide_type
        if section.role == NarrativeRole.COMPARISON:
            slide_type = SlideType.COMPARISON
        elif section.role == NarrativeRole.EVIDENCE:
            slide_type = SlideType.DATA
        else:
            slide_type = SlideType.CONTENT

        # 将supporting_elements转换为TextBlock
        text_blocks = []
        for elem in section.supporting_elements:
            text_blocks.append(
                TextBlock(
                    content=elem.content,
                    level=0 if elem.element_type == "conclusion" else 1,
                    is_bold=(elem.element_type == "conclusion")
                )
            )

        return SlideSpec(
            slide_type=slide_type,
            takeaway_message=section.core_argument,
            narrative_arc=section.role,
            supporting_elements=section.supporting_elements,
            text_blocks=text_blocks
        )

    def _create_summary_slide(self, narrative: Narrative) -> SlideSpec:
        """创建总结页"""
        return SlideSpec(
            slide_type=SlideType.SUMMARY,
            takeaway_message="下一步行动建议",
            narrative_arc=NarrativeRole.CLOSING,
            text_blocks=[
                TextBlock(content="关键结论", level=0, is_bold=True),
                TextBlock(content=narrative.executive_summary, level=1),
                TextBlock(content="行动建议", level=0, is_bold=True),
                TextBlock(content="建议立即启动数字化转型试点项目", level=1),
            ]
        )


def create_hardcoded_narrative() -> Narrative:
    """
    创建硬编码的Narrative用于测试
    模拟Layer 2的输出
    """
    from models import ContentElement

    narrative = Narrative(
        title="数字化转型战略方案",
        executive_summary="通过数字化转型，提升运营效率30%，降低获客成本40%",
        target_audience="公司高层管理者",
        sections=[
            NarrativeSection(
                core_argument="当前业务面临三大核心挑战",
                role=NarrativeRole.PROBLEM,
                supporting_elements=[
                    ContentElement(
                        element_type="fact",
                        content="业务增长放缓，2023年增速仅5%",
                        confidence=0.95
                    ),
                    ContentElement(
                        element_type="data",
                        content="获客成本同比上升45%，ROI持续下降",
                        confidence=0.92
                    ),
                    ContentElement(
                        element_type="fact",
                        content="客户流失率高达18%，高于行业平均12%",
                        confidence=0.88
                    ),
                ],
                transition_to_next="这些挑战的根本原因在于..."
            ),
            NarrativeSection(
                core_argument="根本原因：数字化能力缺失",
                role=NarrativeRole.ANALYSIS,
                supporting_elements=[
                    ContentElement(
                        element_type="opinion",
                        content="系统架构老旧，平均交付周期3个月",
                        confidence=0.90
                    ),
                    ContentElement(
                        element_type="fact",
                        content="数据孤岛严重，12个系统独立运行",
                        confidence=0.95
                    ),
                    ContentElement(
                        element_type="conclusion",
                        content="缺乏统一的客户数据平台",
                        confidence=0.85
                    ),
                ],
                transition_to_next="针对这些问题，我们建议..."
            ),
            NarrativeSection(
                core_argument="解决方案：三步走数字化战略",
                role=NarrativeRole.SOLUTION,
                supporting_elements=[
                    ContentElement(
                        element_type="conclusion",
                        content="第一步：构建统一客户数据平台（CDP）",
                        confidence=0.88
                    ),
                    ContentElement(
                        element_type="conclusion",
                        content="第二步：实现全渠道营销自动化",
                        confidence=0.86
                    ),
                    ContentElement(
                        element_type="conclusion",
                        content="第三步：建立数据驱动决策体系",
                        confidence=0.87
                    ),
                ],
                transition_to_next="实施后预期效果..."
            ),
        ]
    )

    return narrative


def demo_structure_planning():
    """演示结构规划功能"""
    print("=" * 60)
    print("Layer 3: 结构规划演示")
    print("=" * 60)

    # 1. 创建硬编码Narrative（模拟Layer 2输出）
    narrative = create_hardcoded_narrative()

    # 2. 规划结构
    planner = StructurePlanner()
    slides = planner.plan_slides(narrative)

    # 3. 展示结果
    print("\n" + "=" * 60)
    print("📋 生成的PPT结构：")
    print("=" * 60)

    for idx, slide in enumerate(slides, 1):
        print(f"\n第{idx}页 [{slide.slide_type.value}]:")
        print(f"  角色：{slide.narrative_arc.value}")
        print(f"  Takeaway：{slide.takeaway_message}")
        if slide.text_blocks:
            print(f"  内容块数：{len(slide.text_blocks)}")

    print("\n" + "=" * 60)
    print("✅ 结构规划演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    demo_structure_planning()
