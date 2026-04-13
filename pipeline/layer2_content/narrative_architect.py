"""
Layer 2 Step 2: Narrative Architect
将提取的ContentElements组织成有逻辑的叙事结构

使用GLM-5 Plus进行论证结构编排
这是整个流水线最关键的一步，直接决定PPT质量的上限
"""

import sys
from pathlib import Path
from typing import List
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from models import ContentElement, Narrative, NarrativeSection, NarrativeRole
from llm_client import GLMClient


class NarrativeArchitect:
    """
    叙事结构编排器：将提取的元素组织成有逻辑的叙事线

    两步走策略的Step 2：
    - 确定核心论点
    - 组织支撑证据的层次
    - 规划叙事流程
    - 确保连贯性
    """

    def __init__(self, llm_client: GLMClient):
        self.llm = llm_client

    def build_narrative(
        self,
        elements: List[ContentElement],
        title: str = "",
        target_audience: str = "管理层"
    ) -> Narrative:
        """
        将提取的元素组织成完整的叙事结构

        Args:
            elements: ContentExtractor提取的内容元素
            title: PPT标题（可选）
            target_audience: 目标受众

        Returns:
            Narrative: 完整的叙事结构
        """
        print(f"\n🏗️  开始构建叙事结构...")
        print(f"   元素数量: {len(elements)}")
        print(f"   目标受众: {target_audience}")

        # 如果没有标题，根据元素生成一个
        if not title:
            title = self._generate_title(elements)

        # 构建编排提示词
        prompt = self._build_architecture_prompt(elements, title, target_audience)

        # 调用LLM
        response = self.llm.generate(prompt, temperature=0.7, max_tokens=4096)

        if not response.success:
            print(f"❌ LLM调用失败: {response.error}")
            # 返回一个基础的叙事结构
            return self._create_fallback_narrative(elements, title)

        # 解析LLM返回的JSON，传入elements以映射索引
        narrative = self._parse_llm_response(response.content, title, elements)

        print(f"✅ 叙事结构构建完成")
        print(f"   标题: {narrative.title}")
        print(f"   段落数: {len(narrative.sections)}")

        return narrative

    def _generate_title(self, elements: List[ContentElement]) -> str:
        """根据元素生成标题"""
        # 简单策略：使用第一个结论或观点作为标题基础
        for elem in elements:
            if elem.element_type == "conclusion":
                return "业务分析与建议"
        return "内容分析报告"

    def _build_architecture_prompt(
        self,
        elements: List[ContentElement],
        title: str,
        target_audience: str
    ) -> str:
        """构建叙事编排提示词"""

        # 格式化元素列表
        elements_text = "\n".join([
            f"- [{elem.element_type}] {elem.content} (置信度: {elem.confidence:.2f})"
            for elem in elements
        ])

        prompt = f"""你是一个专业的咨询顾问，擅长构建清晰的论证结构。请基于以下提取的内容元素，构建一个完整的PPT叙事结构。

## PPT标题
{title}

## 目标受众
{target_audience}

## 提取的内容元素
{elements_text}

## 任务要求
请将这些元素组织成一个有逻辑的叙事结构，要求：

1. **明确的核心论点**：整个PPT要传达什么核心信息？
2. **分层次的论证**：每个段落有明确的论点和支撑证据
3. **流畅的叙事**：段落之间有逻辑过渡
4. **符合咨询风格**：每页一个takeaway，所有元素服务于这个takeaway

## 叙事结构建议
- 开篇（Opening）：引出问题和背景
- 问题陈述（Problem）：明确面临的挑战
- 分析论证（Analysis）：深入分析原因
- 方案提出（Solution）：提出解决方案
- 总结收尾（Closing）：总结和建议

## 输出格式
请以JSON格式返回，结构如下：

```json
{{
  "executive_summary": "一句话总结核心观点",
  "overall_tone": "professional",
  "sections": [
    {{
      "core_argument": "这个段落的核心论点（将成为PPT某一页的takeaway）",
      "role": "opening | problem_statement | context | evidence | analysis | comparison | counterpoint | solution | recommendation | closing",
      "supporting_element_indices": [0, 1, 2],
      "transition_to_next": "到下一段的过渡逻辑"
    }}
  ]
}}
```

注意：
- `supporting_element_indices` 是元素列表的索引（从0开始）
- 选择最相关的元素支持每个段落的论点
- 不要重复使用元素
- 每个段落应该有3-5个支撑元素

请直接输出JSON，不要添加解释文字。"""

        return prompt

    def _parse_llm_response(self, response_text: str, title: str, elements: List[ContentElement] = None) -> Narrative:
        """解析LLM返回的JSON"""
        try:
            # 尝试提取JSON部分
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()

            # 解析JSON
            data = json.loads(json_text)

            # 转换为Narrative对象
            sections = []
            for section_data in data.get("sections", []):
                # 解析role
                role_str = section_data.get("role", "evidence")
                try:
                    role = NarrativeRole(role_str)
                except ValueError:
                    role = NarrativeRole.EVIDENCE

                # 从indices映射到实际的ContentElement
                supporting = []
                indices = section_data.get("supporting_element_indices", [])
                if elements and indices:
                    for idx in indices:
                        idx = int(idx)
                        if 0 <= idx < len(elements):
                            supporting.append(elements[idx])

                # 如果映射后仍为空，用core_argument作为fallback内容
                if not supporting and elements:
                    # 从未分配的元素中挑选相关的
                    used_indices = set()
                    for s in sections:
                        for e in s.supporting_elements:
                            if e in elements:
                                used_indices.add(elements.index(e))
                    remaining = [e for i, e in enumerate(elements) if i not in used_indices]
                    supporting = remaining[:3]

                section = NarrativeSection(
                    core_argument=section_data.get("core_argument", ""),
                    role=role,
                    supporting_elements=supporting,
                    transition_to_next=section_data.get("transition_to_next", "")
                )
                sections.append(section)

            narrative = Narrative(
                title=title,
                executive_summary=data.get("executive_summary", ""),
                sections=sections,
                overall_tone=data.get("overall_tone", "professional")
            )

            return narrative

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON解析失败: {str(e)}")
            print(f"   原始响应: {response_text[:200]}...")
            return self._create_fallback_narrative([], title)

        except Exception as e:
            print(f"⚠️ 解析错误: {str(e)}")
            return self._create_fallback_narrative([], title)

    def _create_fallback_narrative(
        self,
        elements: List[ContentElement],
        title: str
    ) -> Narrative:
        """创建后备的叙事结构（当LLM调用失败时）"""
        return Narrative(
            title=title,
            executive_summary="基于提供的内容进行分析",
            sections=[
                NarrativeSection(
                    core_argument="核心观点",
                    role=NarrativeRole.EVIDENCE,
                    supporting_elements=elements[:5] if len(elements) > 5 else elements
                )
            ]
        )


def test_narrative_architect():
    """测试叙事结构编排器"""
    print("=" * 70)
    print("测试Layer 2 Step 2: 叙事结构编排器")
    print("=" * 70)

    try:
        # 初始化LLM客户端
        llm_client = GLMClient()
        architect = NarrativeArchitect(llm_client)

        # 创建测试元素（模拟ContentExtractor的输出）
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
            ContentElement(
                element_type="conclusion",
                content="通过AI技术实现营销自动化，预计可降低获客成本40%",
                confidence=0.86,
                topics=["AI", "成本"]
            ),
        ]

        # 构建叙事结构
        narrative = architect.build_narrative(
            elements,
            title="数字化转型战略方案",
            target_audience="公司高层管理者"
        )

        # 显示结果
        print("\n" + "=" * 70)
        print("叙事结构构建结果:")
        print("=" * 70)

        print(f"\n标题: {narrative.title}")
        print(f"摘要: {narrative.executive_summary}")
        print(f"\n共 {len(narrative.sections)} 个段落:\n")

        for idx, section in enumerate(narrative.sections, 1):
            print(f"{idx}. [{section.role.value}] {section.core_argument}")
            if section.transition_to_next:
                print(f"   → 过渡: {section.transition_to_next}")

        # LLM统计
        stats = llm_client.get_stats()
        print(f"\n" + "=" * 70)
        print("LLM使用统计:")
        print("=" * 70)
        print(f"  总请求数: {stats['total_requests']}")
        print(f"  Token使用: {stats['total_tokens_used']}")
        print(f"  成功率: {stats['success_rate']:.1f}%")

    except ValueError as e:
        print(f"\n⚠️ 配置错误: {str(e)}")
        print("   请设置环境变量: export GLM_API_KEY='your-api-key'")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_narrative_architect()
