"""
端到端完整测试：Layer 2 → Layer 3 → Layer 6
演示完整的PPT生成流程
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from models import (
    RawContent, ContentElement, Narrative, NarrativeSection,
    NarrativeRole, PresentationSpec, SlideType
)
from pipeline.layer2_content import NarrativeArchitect
from pipeline.layer3_structure import StructurePlanner
from pipeline.layer6_output import PPTBuilder


def create_sample_narrative() -> Narrative:
    """
    创建示例Narrative（模拟Layer 2的输出）
    如果有GLM API Key，可以使用真实的ContentExtractor和NarrativeArchitect
    """
    print("📝 创建示例叙事结构...")

    elements = [
        ContentElement(
            element_type="fact",
            content="公司2023年营收增长5%，低于行业平均12%",
            confidence=0.95,
            topics=["业绩", "增长"]
        ),
        ContentElement(
            element_type="data",
            content="获客成本同比上升45%，ROI从3.2降至2.3",
            confidence=0.92,
            topics=["成本", "效率"]
        ),
        ContentElement(
            element_type="fact",
            content="客户流失率达到18%，高于行业平均12%",
            confidence=0.88,
            topics=["客户", "流失"]
        ),
        ContentElement(
            element_type="opinion",
            content="系统架构老旧是根本原因，平均交付周期长达3个月",
            confidence=0.90,
            topics=["系统", "效率"]
        ),
        ContentElement(
            element_type="fact",
            content="数据孤岛严重，客户数据分散在12个独立系统中",
            confidence=0.95,
            topics=["数据", "孤岛"]
        ),
        ContentElement(
            element_type="conclusion",
            content="建议立即启动数字化转型项目，构建统一客户数据平台",
            confidence=0.88,
            topics=["转型", "CDP"]
        ),
    ]

    narrative = Narrative(
        title="数字化转型战略方案",
        executive_summary="通过数字化转型，预计可将获客成本降低40%，ROI提升至3.5以上",
        target_audience="公司高层管理者",
        sections=[
            NarrativeSection(
                core_argument="当前业务面临三大核心挑战",
                role=NarrativeRole.PROBLEM,
                supporting_elements=elements[:3],
                transition_to_next="这些挑战的根本原因在于..."
            ),
            NarrativeSection(
                core_argument="根本原因：数字化能力缺失",
                role=NarrativeRole.ANALYSIS,
                supporting_elements=elements[3:5],
                transition_to_next="针对这些问题，我们建议..."
            ),
            NarrativeSection(
                core_argument="解决方案：三步走数字化战略",
                role=NarrativeRole.SOLUTION,
                supporting_elements=[elements[5]],
                transition_to_next="实施后预期效果..."
            ),
        ]
    )

    print(f"✅ 叙事结构创建完成: {narrative.title}")
    return narrative


def test_full_pipeline():
    """测试完整的PPT生成流水线"""
    print("\n" + "🎯" * 35)
    print("  PPT Agent 完整流水线测试")
    print("  Layer 2 → Layer 3 → Layer 6")
    print("🎯" * 35)

    # ========== Layer 2: 内容分析层 ==========
    print("\n" + "=" * 70)
    print("📚 Layer 2: 内容分析层 (Content Analysis)")
    print("=" * 70)

    narrative = create_sample_narrative()

    print(f"\n叙事结构概览:")
    print(f"  标题: {narrative.title}")
    print(f"  摘要: {narrative.executive_summary}")
    print(f"  段落数: {len(narrative.sections)}")

    # ========== Layer 3: 结构规划层 ==========
    print("\n" + "=" * 70)
    print("🏗️  Layer 3: 结构规划层 (Structure Planning)")
    print("=" * 70)

    planner = StructurePlanner()
    slides = planner.plan_slides(narrative)

    print(f"\n生成的SlideSpec列表:")
    for idx, slide in enumerate(slides, 1):
        print(f"\n  第{idx}页 [{slide.slide_type.value}]")
        print(f"    Takeaway: {slide.takeaway_message}")
        print(f"    角色: {slide.narrative_arc.value}")
        if slide.text_blocks:
            print(f"    文本块: {len(slide.text_blocks)} 个")

    # ========== Layer 6: PPT生成层 ==========
    print("\n" + "=" * 70)
    print("🎨 Layer 6: PPT生成层 (PPT Building)")
    print("=" * 70)

    pres_spec = PresentationSpec(
        title=narrative.title,
        slides=slides,
        language="zh"
    )

    builder = PPTBuilder()
    output_path = builder.build(pres_spec)

    # ========== 结果展示 ==========
    print("\n" + "=" * 70)
    print("📊 生成结果")
    print("=" * 70)

    print(f"\n✅ PPT生成成功!")
    print(f"   文件路径: {output_path}")

    # 文件信息
    file_size = Path(output_path).stat().st_size / 1024
    print(f"   文件大小: {file_size:.1f} KB")
    print(f"   页面数量: {len(slides)} 页")

    # ========== 流水线总结 ==========
    print("\n" + "=" * 70)
    print("🎉 流水线测试完成!")
    print("=" * 70)

    print("\n📦 数据流转:")
    print(f"  Narrative (Layer 2)")
    print(f"    ↓ {len(narrative.sections)} 个叙事段落")
    print(f"  List[SlideSpec] (Layer 3)")
    print(f"    ↓ {len(slides)} 个页面")
    print(f"  .pptx 文件 (Layer 6)")
    print(f"    ↓")
    print(f"  {Path(output_path).name} ✅")

    print("\n🎯 每层的职责:")
    print("  Layer 2: 内容提取 + 叙事编排")
    print("  Layer 3: 页面规划 + takeaway分配")
    print("  Layer 6: 布局计算 + PPT生成")

    print("\n💡 下一步优化方向:")
    print("  1. 使用真实LLM (设置GLM_API_KEY)")
    print("  2. 添加Layer 4: 视觉设计 (模板匹配)")
    print("  3. 添加Layer 5: 图表生成 (数据可视化)")
    print("  4. 实现Layer 1: 输入解析 (文件处理)")

    print("\n" + "🎉" * 35)

    return output_path


if __name__ == "__main__":
    test_full_pipeline()
