"""
Layer 2 Step 1: Content Extractor
从RawContent中提取结构化元素（事实/数据/观点/结论）

使用GLM-5 Plus进行智能提取和分类
"""

import sys
from pathlib import Path
from typing import List
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from models import RawContent, ContentElement
from llm_client import GLMClient


class ContentExtractor:
    """
    内容提取器：将非结构化文本提取为结构化元素

    两步走策略的Step 1：
    - 提取事实（facts）
    - 提取数据（data）
    - 提取观点（opinions）
    - 提取结论（conclusions）
    """

    def __init__(self, llm_client: GLMClient):
        self.llm = llm_client

    def extract_elements(self, raw_content: RawContent) -> List[ContentElement]:
        """
        从RawContent提取结构化元素

        Args:
            raw_content: 第1层输出的原始内容

        Returns:
            List[ContentElement]: 分类后的内容元素列表
        """
        print(f"\n🔍 开始内容提取...")
        print(f"   源类型: {raw_content.source_type}")
        print(f"   文本长度: {len(raw_content.raw_text)} 字符")

        # 构建提取提示词
        prompt = self._build_extraction_prompt(raw_content)

        # 调用LLM
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)

        if not response.success:
            print(f"❌ LLM调用失败: {response.error}")
            return []

        # 解析LLM返回的JSON
        elements = self._parse_llm_response(response.content)

        print(f"✅ 提取完成，共 {len(elements)} 个元素")
        for elem in elements:
            print(f"   • [{elem.element_type}] {elem.content[:50]}...")

        return elements

    def _build_extraction_prompt(self, raw_content: RawContent) -> str:
        """构建提取提示词"""
        prompt = f"""你是一个专业的内容分析师。请从以下文本中提取关键信息，并按照指定格式分类。

## 输入文本
{raw_content.raw_text}

## 提取要求
请提取并分类以下四类元素：

1. **事实（fact）**：客观存在的情况、现象、事件
2. **数据（data）**：具体的数字、统计、指标
3. **观点（opinion）**：主观的分析、判断、预测
4. **结论（conclusion）**：推导出的核心结论、建议

## 输出格式
请以JSON数组格式返回，每个元素包含：
- element_type: "fact" | "data" | "opinion" | "conclusion"
- content: 元素内容（简洁明了，每条不超过100字）
- confidence: 置信度（0.0-1.0）
- topics: 相关主题标签（数组，2-3个）

## 示例输出
```json
[
  {{
    "element_type": "fact",
    "content": "公司2023年营收增长5%，低于行业平均12%",
    "confidence": 0.95,
    "topics": ["业绩", "增长"]
  }},
  {{
    "element_type": "data",
    "content": "获客成本同比上升45%，ROI下降至2.3",
    "confidence": 0.92,
    "topics": ["成本", "效率"]
  }}
]
```

请直接输出JSON数组，不要添加任何解释文字。"""

        return prompt

    def _parse_llm_response(self, response_text: str) -> List[ContentElement]:
        """解析LLM返回的JSON"""
        try:
            # 尝试提取JSON部分（处理markdown代码块）
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                if json_end == -1:
                    # 如果没有找到结束标记，尝试截取到最后一个完整的对象
                    json_text = response_text[json_start:].strip()
                    # 尝试找到最后一个完整的对象
                    last_brace = json_text.rfind("}")
                    if last_brace > 0:
                        json_text = json_text[:last_brace+1] + "]"
                else:
                    json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                if json_end == -1:
                    json_text = response_text[json_start:].strip()
                    last_brace = json_text.rfind("}")
                    if last_brace > 0:
                        json_text = json_text[:last_brace+1] + "]"
                else:
                    json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()

            # 解析JSON
            elements_data = json.loads(json_text)

            # 转换为ContentElement对象
            elements = []
            for item in elements_data:
                element = ContentElement(
                    element_type=item.get("element_type", "fact"),
                    content=item.get("content", ""),
                    confidence=item.get("confidence", 0.8),
                    topics=item.get("topics", [])
                )
                elements.append(element)

            return elements

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON解析失败: {str(e)}")
            print(f"   原始响应长度: {len(response_text)} 字符")

            # 尝试使用正则表达式提取有效元素
            try:
                import re
                pattern = r'"element_type":\s*"(fact|data|opinion|conclusion)".*?"content":\s*"([^"]+)"'
                matches = re.findall(pattern, response_text, re.DOTALL)

                elements = []
                for elem_type, content in matches[:10]:  # 最多提取10个
                    elements.append(ContentElement(
                        element_type=elem_type,
                        content=content,
                        confidence=0.8,
                        topics=[]
                    ))

                if elements:
                    print(f"✅ 通过正则表达式提取了 {len(elements)} 个元素")
                    return elements
            except Exception:
                pass

            # 返回空列表而不是抛出异常
            return []

        except Exception as e:
            print(f"⚠️ 解析错误: {str(e)}")
            return []


def test_content_extractor():
    """测试内容提取器"""
    print("=" * 70)
    print("测试Layer 2 Step 1: 内容提取器")
    print("=" * 70)

    try:
        # 初始化LLM客户端
        llm_client = GLMClient()
        extractor = ContentExtractor(llm_client)

        # 创建测试内容
        raw_content = RawContent(
            source_type="text",
            raw_text="""
            公司2023年业务分析报告

            一、业绩回顾
            2023年公司实现营收15.2亿元，同比增长5%，但低于行业平均水平12%。
            其中线上渠道贡献8.3亿元，占比55%。

            二、挑战分析
            获客成本持续上升，同比增加45%，ROI从去年的3.2下降至2.3。
            客户流失率达到18%，高于行业平均的12%。

            三、根本原因
            系统架构老旧，平均需求交付周期长达3个月，难以快速响应市场变化。
            数据孤岛问题严重，客户数据分散在12个独立系统中，缺乏统一视图。

            四、改进方向
            建议立即启动数字化转型项目，构建统一客户数据平台（CDP）。
            通过AI技术实现营销自动化，预计可将获客成本降低40%。
            """,
            detected_language="zh"
        )

        # 提取元素
        elements = extractor.extract_elements(raw_content)

        # 显示结果
        print("\n" + "=" * 70)
        print("提取结果:")
        print("=" * 70)

        for idx, elem in enumerate(elements, 1):
            print(f"\n{idx}. [{elem.element_type}] {elem.content}")
            print(f"   置信度: {elem.confidence:.2f}")
            print(f"   主题: {', '.join(elem.topics)}")

        # 统计
        type_count = {}
        for elem in elements:
            type_count[elem.element_type] = type_count.get(elem.element_type, 0) + 1

        print("\n" + "=" * 70)
        print("统计信息:")
        print("=" * 70)
        for elem_type, count in type_count.items():
            print(f"  {elem_type}: {count} 个")

        # LLM统计
        stats = llm_client.get_stats()
        print(f"\nLLM使用统计:")
        print(f"  总请求数: {stats['total_requests']}")
        print(f"  Token使用: {stats['total_tokens_used']}")

    except ValueError as e:
        print(f"\n⚠️ 配置错误: {str(e)}")
        print("   请设置环境变量: export GLM_API_KEY='your-api-key'")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_content_extractor()
