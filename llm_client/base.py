"""
LLM客户端抽象基类
所有LLM提供商（智谱GLM、DeepSeek、通义千问等）统一接口
"""

import time
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


class LLMError(Exception):
    """LLM调用异常"""

    def __init__(self, message: str, provider: str = "", model: str = "", retryable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.retryable = retryable


@dataclass
class LLMResponse:
    """LLM响应对象"""
    content: str
    usage: Dict[str, Any] = field(default_factory=dict)
    model: str = ""
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


class LLMClient(ABC):
    """
    LLM客户端抽象基类

    所有提供商必须实现generate()方法。
    子类只需关注provider特有的API调用逻辑，重试、统计等由基类统一处理。
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        max_retries: int = 5,
        timeout: int = 120,
    ):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout

        # 统计信息
        self.total_requests = 0
        self.failed_requests = 0
        self.total_tokens_used = 0

    @abstractmethod
    def _call_api(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> LLMResponse:
        """
        Provider特有的API调用逻辑，子类必须实现。

        不需要处理重试，基类的generate()方法会统一处理。
        成功返回LLMResponse，失败抛出异常。
        """
        ...

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """
        生成文本，含统一重试逻辑（指数退避 + 429特殊处理）

        Args:
            prompt: 输入提示
            temperature: 采样温度 (0-1)
            max_tokens: 最大生成token数

        Returns:
            LLMResponse
        """
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                response = self._call_api(prompt, temperature, max_tokens, **kwargs)

                # 更新统计
                self.total_requests += 1
                self.total_tokens_used += response.total_tokens

                response.latency_ms = (time.time() - start_time) * 1000
                return response

            except LLMError:
                raise  # 不可重试的LLMError直接抛出

            except Exception as e:
                self.failed_requests += 1
                err_str = str(e)

                # 401/403 认证错误不重试，直接返回可读消息
                is_auth_error = "401" in err_str or "403" in err_str or "Unauthorized" in err_str
                if is_auth_error:
                    latency = (time.time() - start_time) * 1000
                    return LLMResponse(
                        content="",
                        usage={},
                        model=self.model,
                        latency_ms=latency,
                        success=False,
                        error=f"API Key 认证失败（模型: {self.model}）。请在「系统设置」中检查该阶段的 API Key 是否正确、是否过期。",
                    )

                if attempt == self.max_retries - 1:
                    latency = (time.time() - start_time) * 1000
                    return LLMResponse(
                        content="",
                        usage={},
                        model=self.model,
                        latency_ms=latency,
                        success=False,
                        error=err_str,
                    )

                # 429限流用更长等待
                is_rate_limit = "429" in err_str or "rate" in err_str.lower()
                if is_rate_limit:
                    wait = 10 * (2 ** attempt) + random.uniform(1, 5)
                else:
                    wait = 2 ** attempt + random.uniform(0, 1)
                time.sleep(wait)

        return LLMResponse(
            content="",
            usage={},
            model=self.model,
            latency_ms=0,
            success=False,
            error="Max retries exceeded",
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计信息"""
        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "total_tokens_used": self.total_tokens_used,
            "success_rate": (
                (self.total_requests - self.failed_requests) / self.total_requests * 100
                if self.total_requests > 0 else 0
            ),
        }

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        估算文本的token数量
        简单规则：中文约1.5字符/token，英文约4字符/token
        """
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_chars = len(text) - chinese_chars
        return max(int(chinese_chars / 1.5 + english_chars / 4), 100)
