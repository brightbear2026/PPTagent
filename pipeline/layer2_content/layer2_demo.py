"""
Layer 2 完整测试：内容分析层端到端流程
测试两步走策略：ContentExtractor → NarrativeArchitect
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from models import RawContent, ContentElement, Narrative, NarrativeSection, NarrativeRole
from llm_client import GLMClient
from pipeline.layer2_content import ContentExtractor, NarrativeArchitect


def test_layer2_without_llm():
    """
    硬编码演示版本（无需GLM API Key）
    展示Layer 2的输入输出格式
    """
    print("\n" + "🚀" * 35)
    print("  Layer 2 内容分析层 - 演示模式")
    print("🚀" * 35)

    # ========== Step 1: 内容提取（模拟）==========
    print("\n📝 Step 1: 内容提取器 (ContentExtractor)")
    print("=" * 70)

    # 模拟ContentExtractor的输出
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

    print(f"\n提取到 {len(elements)} 个内容元素:\n")

    for idx, elem in enumerate(elements, 1):
        print(f"{idx}. [{elem.element_type}] {elem.content}")
        print(f"   置信度: {elem.confidence:.2f}, 主题: {', '.join(elem.topics)}\n")

    # ========== Step 2: 叙事结构编排（模拟）==========
    print("\n🏗️  Step 2: 叙事结构编排 (NarrativeArchitect)")
    print("=" * 70)

    # 模拟NarrativeArchitect的输出
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

    print(f"\n构建的叙事结构:\n")
    print(f"标题: {narrative.title}")
    print(f"摘要: {narrative.executive_summary}")
    print(f"\n共 {len(narrative.sections)} 个段落:\n")

    for idx, section in enumerate(narrative.sections, 1):
        print(f"第{idx}段 [{section.role.value}]")
        print(f"  核心论点: {section.core_argument}")
        print(f"  支撑元素: {len(section.supporting_elements)} 个")
        if section.transition_to_next:
            print(f"  → 过渡: {section.transition_to_next}")
        print()

    # ========== 输出验证 ==========
    print("=" * 70)
    print("✅ Layer 2 演示完成")
    print("=" * 70)

    print("\n📊 输出对象: Narrative")
    print("   - 可以直接传递给 Layer 3 (StructurePlanner)")
    print("   - 每个section都有明确的core_argument")
    print("   - 所有section都有narrative role")

    print("\n💡 提示:")
    print("   - 要使用真实LLM调用，请设置GLM_API_KEY环境变量")
    print("   - export GLM_API_KEY='your-api-key'")
    print("   - 然后运行: python3 pipeline/layer2_content/layer2_full_test.py")

    return narrative


def test_layer2_full_pipeline():
    """
    完整测试（需要GLM API Key）
    使用真实的LLM调用
    """
    print("\n" + "🚀" * 35)
    print("  Layer 2 内容分析层 - 完整流程测试")
    print("🚀" * 35)

    try:
        # 初始化
        print("\n步骤0: 初始化组件...")
        llm_client = GLMClient()
        extractor = ContentExtractor(llm_client)
        architect = NarrativeArchitect(llm_client)
        print("✅ 组件初始化完成")

        # 准备测试数据
        print("\n步骤1: 准备原始内容...")
        raw_content = RawContent(
            source_type="text",
            raw_text="""
            2023年公司业务分析报告

            一、业绩回顾
            2023年公司实现营收15.2亿元，同比增长5%，但低于行业平均水平12%。
            其中线上渠道贡献8.3亿元，占比55%。线下渠道持续萎缩，同比下降8%。

            二、核心挑战
            1. 获客成本持续上升
            - 线上获客成本同比增加45%，从120元/人提升至174元/人
            - ROI从去年的3.2下降至2.3，低于行业平均3.5
            - 主要渠道（信息流、搜索）成本均上涨40%以上

            2. 客户流失率居高不下
            - 整体客户流失率达到18%，高于行业平均12%
            - 新客户首年流失率高达32%
            - 流失客户中65%表示"服务响应慢"是主要原因

            三、根本原因分析
            1. 系统架构老旧
            - 平均需求交付周期长达3个月，无法快速响应市场
            - 核心系统平均运行8年，技术栈落后
            - 系统间集成困难，新增功能开发成本高

            2. 数据孤岛严重
            - 客户数据分散在12个独立系统中，缺乏统一视图
            - 营销数据与销售数据无法实时打通
            - 数据提取平均需要2-3天

            四、改进方向
            1. 立即启动数字化转型项目
            2. 构建统一客户数据平台（CDP）
            3. 通过AI技术实现营销自动化
            4. 预计可将获客成本降低40%，ROI提升至3.5以上
            """,
            detected_language="zh"
        )
        print(f"✅ 原始内容准备完成，长度: {len(raw_content.raw_text)} 字符")

        # Step 1: 内容提取
        print("\n步骤2: 内容提取 (ContentExtractor)...")
        elements = extractor.extract_elements(raw_content)

        if not elements:
            print("⚠️  内容提取失败，使用fallback数据")
            return test_layer2_without_llm()

        # Step 2: 叙事结构编排
        print("\n步骤3: 叙事结构编排 (NarrativeArchitect)...")
        narrative = architect.build_narrative(
            elements,
            title="数字化转型战略方案",
            target_audience="公司高层管理者"
        )

        # 显示结果
        print("\n" + "=" * 70)
        print("最终输出:")
        print("=" * 70)

        print(f"\n标题: {narrative.title}")
        print(f"摘要: {narrative.executive_summary}")
        print(f"\n共 {len(narrative.sections)} 个段落:\n")

        for idx, section in enumerate(narrative.sections, 1):
            print(f"第{idx}段 [{section.role.value}]")
            print(f"  核心论点: {section.core_argument}")
            if section.transition_to_next:
                print(f"  → 过渡: {section.transition_to_next}")

        # LLM统计
        stats = llm_client.get_stats()
        print(f"\n" + "=" * 70)
        print("LLM使用统计:")
        print("=" * 70)
        print(f"  总请求数: {stats['total_requests']}")
        print(f"  Token使用: {stats['total_tokens_used']}")
        print(f"  成功率: {stats['success_rate']:.1f}%")

        print("\n" + "🎉" * 35)
        print("  Layer 2 完整流程测试成功！")
        print("🎉" * 35)

    except ValueError as e:
        print(f"\n⚠️  配置错误: {str(e)}")
        print("   请检查GLM_API_KEY环境变量是否正确设置")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 检查是否设置了GLM_API_KEY
    if os.getenv("GLM_API_KEY"):
        print("🔑 检测到GLM_API_KEY，运行完整测试...")
        test_layer2_full_pipeline()
    else:
        print("⚠️  未检测到GLM_API_KEY，运行硬编码演示版本...")
        test_layer2_without_llm()
