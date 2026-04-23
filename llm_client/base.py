"""
LLM客户端抽象基类
所有LLM提供商（智谱GLM、DeepSeek、通义千问等）统一接口
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

try:
    from tenacity import (
        Retrying,
        retry_if_exception,
        stop_after_attempt,
        wait_random_exponential,
        before_sleep_log,
    )
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chat / tool-use 数据类型（供 ReAct Agent 使用）
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """LLM返回的工具调用请求"""
    call_id: str           # provider 返回的调用 ID
    function_name: str     # 要调用的工具函数名
    arguments: str         # JSON 字符串，工具参数


@dataclass
class ToolDefinition:
    """向 LLM 声明的工具定义"""
    name: str
    description: str
    parameters: dict       # JSON Schema


@dataclass
class ChatMessage:
    """多轮对话消息"""
    role: str              # "system" | "user" | "assistant" | "tool"
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None    # role="assistant" 时存在
    tool_call_id: Optional[str] = None             # role="tool" 时必须匹配
    name: Optional[str] = None                     # role="tool" 时的工具名

    def to_dict(self) -> dict:
        """转换为 provider API 格式（OpenAI 兼容）"""
        d: dict = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.call_id,
                    "type": "function",
                    "function": {
                        "name": tc.function_name,
                        "arguments": tc.arguments,
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d


@dataclass
class ChatResponse:
    """chat() 调用的返回值"""
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: str = ""        # "stop" | "tool_calls" | "length"
    usage: Dict[str, Any] = field(default_factory=dict)
    model: str = ""
    success: bool = True
    error: Optional[str] = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


# ---------------------------------------------------------------------------

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


def _is_retryable(exc: Exception) -> bool:
    """401/403 认证错误不重试；其他异常（包括429/5xx/timeout）都重试。"""
    err = str(exc)
    return not any(x in err for x in ("401", "403", "Unauthorized", "InvalidAuthenticationError"))


class LLMClient(ABC):
    """
    LLM客户端抽象基类

    所有提供商必须实现generate()方法。
    子类只需关注provider特有的API调用逻辑，重试由 tenacity 统一处理。
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        max_retries: int = 3,
        timeout: int = 60,
        provider: str = "",
    ):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self.provider = provider  # 用于 ProviderGate 并发控制

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

    def _call_chat_api(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]],
        temperature: float,
        max_tokens: int,
    ) -> ChatResponse:
        """
        Provider特有的多轮对话+工具调用API。子类可选覆盖。

        默认实现：将最后一条用户消息提取为 prompt 调用 generate()，
        不支持 tools。子类应覆盖此方法以支持 tool_use。
        """
        # Fallback: 拼接所有消息为单一 prompt
        parts = []
        for msg in messages:
            if msg.content:
                prefix = {"system": "[系统]", "user": "[用户]", "assistant": "[助手]"}.get(msg.role, "")
                parts.append(f"{prefix} {msg.content}")
        prompt = "\n".join(parts)
        resp = self._call_api(prompt, temperature, max_tokens)
        return ChatResponse(
            content=resp.content,
            finish_reason="stop",
            usage=resp.usage,
            model=resp.model,
            success=resp.success,
            error=resp.error,
        )

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """生成文本（tenacity 指数退避重试 + ProviderGate 并发控制）。"""
        import time
        from . import provider_gate

        start_time = time.time()
        provider_gate.acquire(self.provider)
        try:
            self.total_requests += 1
            response = self._call_with_tenacity_generate(prompt, temperature, max_tokens, **kwargs)
            self.total_tokens_used += response.total_tokens
            response.latency_ms = (time.time() - start_time) * 1000
            return response
        except LLMError:
            raise
        except Exception as e:
            self.failed_requests += 1
            err_str = str(e)
            latency = (time.time() - start_time) * 1000
            if any(x in err_str for x in ("401", "403", "Unauthorized")):
                return LLMResponse(
                    content="", usage={}, model=self.model, latency_ms=latency,
                    success=False,
                    error=f"API Key 认证失败（模型: {self.model}）。请在「系统设置」中检查该阶段的 API Key 是否正确、是否过期。",
                )
            return LLMResponse(content="", usage={}, model=self.model,
                               latency_ms=latency, success=False, error=err_str)
        finally:
            provider_gate.release(self.provider)

    def _call_with_tenacity_generate(self, prompt, temperature, max_tokens, **kwargs):
        """tenacity 包装的 _call_api（generate 路径）。"""
        if HAS_TENACITY:
            for attempt in Retrying(
                wait=wait_random_exponential(multiplier=2, min=2, max=60),
                stop=stop_after_attempt(self.max_retries),
                retry=retry_if_exception(_is_retryable),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    return self._call_api(prompt, temperature, max_tokens, **kwargs)
        else:
            return self._call_api(prompt, temperature, max_tokens, **kwargs)

    def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """多轮对话（tenacity 指数退避重试 + ProviderGate 并发控制）。"""
        from . import provider_gate

        provider_gate.acquire(self.provider)
        try:
            self.total_requests += 1
            response = self._call_with_tenacity_chat(messages, tools, temperature, max_tokens)
            self.total_tokens_used += response.total_tokens
            return response
        except LLMError:
            raise
        except Exception as e:
            self.failed_requests += 1
            err_str = str(e)
            if any(x in err_str for x in ("401", "403", "Unauthorized")):
                return ChatResponse(
                    success=False,
                    error=f"API Key 认证失败（模型: {self.model}）。请检查 API Key 是否正确。",
                )
            return ChatResponse(success=False, error=err_str)
        finally:
            provider_gate.release(self.provider)

    def _call_with_tenacity_chat(self, messages, tools, temperature, max_tokens):
        """tenacity 包装的 _call_chat_api（chat 路径）。"""
        if HAS_TENACITY:
            for attempt in Retrying(
                wait=wait_random_exponential(multiplier=2, min=2, max=60),
                stop=stop_after_attempt(self.max_retries),
                retry=retry_if_exception(_is_retryable),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    return self._call_chat_api(messages, tools, temperature, max_tokens)
        else:
            return self._call_chat_api(messages, tools, temperature, max_tokens)

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
