"""
智谱GLM适配器
继承LLMClient抽象基类，使用zhipuai SDK或HTTP fallback
"""

import os
from typing import Optional

from .base import LLMClient, LLMResponse

try:
    from zhipuai import ZhipuAI
    HAS_SDK = True
except ImportError:
    HAS_SDK = False


class ZhipuClient(LLMClient):
    """
    智谱GLM API客户端

    继承自LLMClient，实现智谱AI特有的API调用逻辑。
    重试、统计等通用功能由基类提供。
    """

    API_BASE = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "glm-4-plus",
        max_retries: int = 5,
        timeout: int = 120,
    ):
        resolved_key = api_key or os.getenv("GLM_API_KEY") or os.getenv("ZHIPU_API_KEY")
        if not resolved_key:
            raise ValueError(
                "智谱API Key未设置。请设置 ZHIPU_API_KEY 或 GLM_API_KEY 环境变量"
            )

        super().__init__(
            api_key=resolved_key,
            model=model,
            max_retries=max_retries,
            timeout=timeout,
        )

        if HAS_SDK:
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
        """智谱AI API调用"""
        top_p = kwargs.get("top_p", 0.9)

        if HAS_SDK and self._sdk_client:
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
            f"{self.API_BASE}/chat/completions",
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
