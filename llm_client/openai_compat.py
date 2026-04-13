"""
OpenAI兼容适配器
通过base_url切换覆盖DeepSeek、通义千问、Moonshot等国内模型提供商
"""

import os
import re
from typing import Optional

from .base import LLMClient, LLMResponse

try:
    from openai import OpenAI
    HAS_OPENAI_SDK = True
except ImportError:
    HAS_OPENAI_SDK = False

# 各提供商默认配置
PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-r1",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "tongyi": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-max",
        "env_key": "TONGYI_API_KEY",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "env_key": "MOONSHOT_API_KEY",
    },
}


class OpenAICompatClient(LLMClient):
    """
    OpenAI兼容协议客户端

    通过切换base_url覆盖国内主流LLM提供商：
    - DeepSeek (api.deepseek.com)
    - 通义千问 (dashscope.aliyuncs.com)
    - Moonshot (api.moonshot.cn)
    - 任何OpenAI兼容端点
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: Optional[str] = None,
        max_retries: int = 5,
        timeout: int = 120,
    ):
        # 根据provider确定默认值
        defaults = {}
        if provider and provider in PROVIDER_DEFAULTS:
            defaults = PROVIDER_DEFAULTS[provider]

        # 解析api_key：显式传入 > 环境变量
        resolved_key = api_key
        if not resolved_key and defaults:
            resolved_key = os.getenv(defaults["env_key"])
        if not resolved_key:
            resolved_key = os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            provider_hint = provider or "openai-compatible"
            raise ValueError(
                f"API Key未设置。请设置对应提供商的环境变量 "
                f"或传入api_key参数 (provider={provider_hint})"
            )

        resolved_model = model or defaults.get("model", "gpt-4")
        resolved_url = base_url or defaults.get("base_url")

        super().__init__(
            api_key=resolved_key,
            model=resolved_model,
            max_retries=max_retries,
            timeout=timeout,
        )

        self.base_url = resolved_url

        if HAS_OPENAI_SDK:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        else:
            self._client = None

    def _call_api(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> LLMResponse:
        """OpenAI兼容API调用"""
        top_p = kwargs.get("top_p", 0.9)
        messages = kwargs.get("messages", [{"role": "user", "content": prompt}])

        if self._client:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )

            content = response.choices[0].message.content or ""

            # DeepSeek-R1: strip <think'> reasoning tags from content
            if '<think' in content:
                content = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()

            return LLMResponse(
                content=content,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                model=self.model,
                success=True,
            )

        # HTTP fallback（无openai SDK时使用requests）
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
        }

        base = self.base_url or "https://api.openai.com/v1"
        resp = requests.post(
            f"{base}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"].get("content") or ""

        # DeepSeek-R1: strip <think'> reasoning tags
        if '<think' in content:
            content = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', content, flags=re.DOTALL).strip()

        return LLMResponse(
            content=content,
            usage=data.get("usage", {}),
            model=self.model,
            success=True,
        )
