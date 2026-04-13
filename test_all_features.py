"""
PPT Agent 功能测试脚本
测试所有已实现的模块
"""

import sys
from pathlib import Path

# 确保可以导入项目模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from models import (
    SlideSpec, PresentationSpec, Narrative, NarrativeSection,
    SlideType, NarrativeRole, TextBlock, ContentElement
)
from pipeline.layer6_output import PPTBuilder
from pipeline.layer3_structure import StructurePlanner


def print_section(title: str):
    """打印分隔符"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_models():
    """测试1：数据模型"""
    print_section("测试1：数据模型导入与创建")

    # 测试创建SlideSpec
    slide = SlideSpec(
        slide_type=SlideType.CONTENT,
        takeaway_message="这是一个测试页面",
        narrative_arc=NarrativeRole.EVIDENCE,
        text_blocks=[
            TextBlock(content="支持证据1", level=0),
            TextBlock(content="详细说明", level=1),
        ]
    )
    print(f"✅ 创建SlideSpec成功: {slide.slide_id}")
    print(f"   类型: {slide.slide_type.value}")
    print(f"   Takeaway: {slide.takeaway_message}")
    print(f"   角色: {slide.narrative_arc.value}")

    # 测试创建Narrative
    narrative = Narrative(
        title="测试演示文稿",
        executive_summary="这是一个测试摘要",
        sections=[
            NarrativeSection(
                core_argument="第一个论点",
                role=NarrativeRole.PROBLEM,
                supporting_elements=[
                    ContentElement(element_type="fact", content="事实1")
                ]
            )
        ]
    )
    print(f"\n✅ 创建Narrative成功")
    print(f"   标题: {narrative.title}")
    print(f"   段落数: {len(narrative.sections)}")


def test_structure_planner():
    """测试2：结构规划层"""
    print_section("测试2：结构规划层 (Layer 3)")

    # 创建测试Narrative
    narrative = Narrative(
        title="AI驱动的业务创新",
        executive_summary="通过AI技术实现业务流程自动化，提升效率50%",
        sections=[
            NarrativeSection(
                core_argument="传统业务流程效率低下",
                role=NarrativeRole.PROBLEM,
                supporting_elements=[
                    ContentElement(element_type="data", content="人工处理平均耗时4小时"),
                    ContentElement(element_type="fact", content="错误率高达15%"),
                ]
            ),
            NarrativeSection(
                core_argument="AI方案可以大幅提效",
                role=NarrativeRole.SOLUTION,
                supporting_elements=[
                    ContentElement(element_type="conclusion", content="部署AI后处理时间降至30分钟"),
                    ContentElement(element_type="conclusion", content="准确率提升至98%"),
                ]
            ),
        ]
    )

    # 使用StructurePlanner生成slides
    planner = StructurePlanner()
    slides = planner.plan_slides(narrative)

    print(f"\n✅ 结构规划完成，共 {len(slides)} 页:")
    for idx, slide in enumerate(slides, 1):
        print(f"\n  第{idx}页 [{slide.slide_type.value}]")
        print(f"    Takeaway: {slide.takeaway_message}")
        print(f"    角色: {slide.narrative_arc.value}")


def test_ppt_builder():
    """测试3：PPT生成"""
    print_section("测试3：PPT生成 (Layer 6)")

    # 创建演示PPT
    pres_spec = PresentationSpec(
        title="AI业务创新方案",
        subtitle="测试演示",
        language="zh"
    )

    # 第1页：标题页
    pres_spec.slides.append(SlideSpec(
        slide_type=SlideType.TITLE,
        takeaway_message="AI驱动的业务创新方案",
        narrative_arc=NarrativeRole.OPENING
    ))

    # 第2页：挑战
    pres_spec.slides.append(SlideSpec(
        slide_type=SlideType.CONTENT,
        takeaway_message="传统业务面临三大挑战",
        narrative_arc=NarrativeRole.PROBLEM,
        text_blocks=[
            TextBlock(content="处理效率低：人工处理平均4小时", level=0),
            TextBlock(content="错误率高：人工错误率达15%", level=0),
            TextBlock(content="成本居高不下：人力成本每年增长20%", level=0),
        ],
        source_note="公司内部数据，2024Q1"
    ))

    # 第3页：解决方案
    pres_spec.slides.append(SlideSpec(
        slide_type=SlideType.CONTENT,
        takeaway_message="AI解决方案实现质的飞跃",
        narrative_arc=NarrativeRole.SOLUTION,
        text_blocks=[
            TextBlock(content="处理时间：4小时 → 30分钟", level=0, is_bold=True),
            TextBlock(content="准确率：85% → 98%", level=0, is_bold=True),
            TextBlock(content="成本降低：40%", level=0, is_bold=True),
        ],
        source_note="试点项目数据，2024Q1"
    ))

    # 生成PPT
    builder = PPTBuilder()
    output_path = builder.build(pres_spec)

    print(f"\n✅ PPT生成成功!")
    print(f"   文件路径: {output_path}")

    # 检查文件大小
    file_size = Path(output_path).stat().st_size
    print(f"   文件大小: {file_size / 1024:.1f} KB")


def test_full_pipeline():
    """测试4：完整流水线 (Layer 3 + Layer 6)"""
    print_section("测试4：完整流水线 (Narrative → Slides → PPT)")

    # Step 1: 创建Narrative
    print("\nStep 1: 创建Narrative...")
    narrative = Narrative(
        title="完整流程测试演示",
        executive_summary="从Narrative到PPT的完整测试",
        sections=[
            NarrativeSection(
                core_argument="第一部分：背景与挑战",
                role=NarrativeRole.CONTEXT,
                supporting_elements=[
                    ContentElement(element_type="fact", content="市场环境快速变化"),
                    ContentElement(element_type="data", content="竞争加剧，利润率下降5%"),
                ]
            ),
            NarrativeSection(
                core_argument="第二部分：解决方案",
                role=NarrativeRole.SOLUTION,
                supporting_elements=[
                    ContentElement(element_type="conclusion", content="采用新技术栈"),
                    ContentElement(element_type="conclusion", content="重构业务流程"),
                ]
            ),
            NarrativeSection(
                core_argument="第三部分：预期效果",
                role=NarrativeRole.CLOSING,
                supporting_elements=[
                    ContentElement(element_type="data", content="效率提升30%"),
                    ContentElement(element_type="data", content="成本降低25%"),
                ]
            ),
        ]
    )
    print("✅ Narrative创建完成")

    # Step 2: 结构规划
    print("\nStep 2: 结构规划 (Layer 3)...")
    planner = StructurePlanner()
    slides = planner.plan_slides(narrative)
    print(f"✅ 生成 {len(slides)} 个SlideSpec")

    # Step 3: 构建PPT
    print("\nStep 3: 构建PPT (Layer 6)...")
    pres_spec = PresentationSpec(
        title="完整流程测试",
        slides=slides
    )

    builder = PPTBuilder()
    output_path = builder.build(pres_spec)

    print(f"\n✅ 完整流水线测试成功!")
    print(f"   Narrative → {len(slides)} Slides → PPT")
    print(f"   输出文件: {output_path}")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "🚀" * 35)
    print("  PPT Agent 功能测试套件")
    print("🚀" * 35)

    try:
        test_models()
        test_structure_planner()
        test_ppt_builder()
        test_full_pipeline()

        print("\n" + "🎉" * 35)
        print("  所有测试通过！")
        print("🎉" * 35)

        print("\n📁 生成的PPT文件:")
        output_dir = Path("output")
        if output_dir.exists():
            for ppt_file in output_dir.glob("*.pptx"):
                size = ppt_file.stat().st_size / 1024
                print(f"   • {ppt_file.name} ({size:.1f} KB)")

        print("\n💡 提示:")
        print("   1. 可以打开output目录下的.pptx文件查看效果")
        print("   2. 所有硬编码内容都可以正常显示")
        print("   3. 下一步：实现Layer 2（内容分析）+ LLM调用")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
