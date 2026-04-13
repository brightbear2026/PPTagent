"""
GLM-5 Plus API 客户端
智谱AI的API封装，继承LLMClient抽象基类
"""

import os
from typing import Optional

from .base import LLMClient, LLMResponse

try:
    from zhipuai import ZhipuAI
    USE_SDK = True
except ImportError:
    USE_SDK = False


class GLMClient(LLMClient):
    """
    GLM-5 Plus API客户端

    继承自LLMClient，实现智谱AI特有的API调用逻辑。
    重试、统计等通用功能由基类提供。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "glm-5.1",
        max_retries: int = 5,
        timeout: int = 120,
    ):
        resolved_key = api_key or os.getenv("GLM_API_KEY")
        if not resolved_key:
            raise ValueError("GLM API Key未设置。请设置GLM_API_KEY环境变量或传入api_key参数")

        super().__init__(
            api_key=resolved_key,
            model=model,
            max_retries=max_retries,
            timeout=timeout,
        )

        # 初始化SDK客户端
        if USE_SDK:
            self._sdk_client = ZhipuAI(api_key=self.api_key)
        else:
            self._sdk_client = None

    def _call_api(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> LLMResponse:
        """智谱AI特有的API调用"""
        top_p = kwargs.get("top_p", 0.9)

        if USE_SDK and self._sdk_client:
            response = self._sdk_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                model=self.model,
                success=True,
            )

        else:
            # HTTP fallback
            import requests

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
            }

            resp = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                usage=data.get("usage", {}),
                model=self.model,
                success=True,
            )


def test_glm_client():
    """测试GLM客户端"""
    print("=" * 60)
    print("测试GLM-5 Plus API客户端")
    print("=" * 60)

    try:
        client = GLMClient()
        print("✅ 客户端初始化成功")

        prompt = "请用一句话描述什么是数字化转型？"
        print(f"\n📝 测试提示：{prompt}")

        response = client.generate(prompt, max_tokens=100)

        if response.success:
            print(f"\n✅ 生成成功:")
            print(f"   响应: {response.content}")
            print(f"   Token使用: {response.usage}")
            print(f"   延迟: {response.latency_ms:.0f}ms")
        else:
            print(f"\n❌ 生成失败: {response.error}")

        stats = client.get_stats()
        print(f"\n📊 统计信息:")
        for key, value in stats.items():
            print(f"   {key}: {value}")

    except ValueError as e:
        print(f"\n⚠️ 配置错误: {str(e)}")
        print("   请设置环境变量: export GLM_API_KEY='your-api-key'")
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_glm_client()
