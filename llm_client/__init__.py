"""
LLM客户端封装层
统一管理多提供商LLM调用，提供重试、超时、成本控制等功能
"""

from .base import (
    LLMClient, LLMResponse, LLMError,
    ChatMessage, ChatResponse, ToolCall, ToolDefinition,
)
from .glm_client import GLMClient
from .zhipu import ZhipuClient
from .openai_compat import OpenAICompatClient
from .factory import get_client, get_client_for_stage, PROVIDER_MAP, STAGE_PROVIDER_MAP

__all__ = [
    "LLMClient", "LLMResponse", "LLMError",
    "ChatMessage", "ChatResponse", "ToolCall", "ToolDefinition",
    "GLMClient", "ZhipuClient", "OpenAICompatClient",
    "get_client", "get_client_for_stage",
    "PROVIDER_MAP", "STAGE_PROVIDER_MAP",
]
