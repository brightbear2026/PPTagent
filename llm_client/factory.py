"""
LLM Provider工厂
根据provider名称创建对应的LLMClient实例
"""

from typing import Optional

from .base import LLMClient
from .zhipu import ZhipuClient
from .openai_compat import OpenAICompatClient, PROVIDER_DEFAULTS

# Provider -> Adapter类映射
PROVIDER_MAP = {
    "zhipu": ZhipuClient,
    "glm": ZhipuClient,
    "deepseek": OpenAICompatClient,
    "tongyi": OpenAICompatClient,
    "qwen": OpenAICompatClient,
    "moonshot": OpenAICompatClient,
    "openai": OpenAICompatClient,
    "custom": OpenAICompatClient,
}

# Pipeline阶段 -> 默认Provider映射
STAGE_PROVIDER_MAP = {
    "layer2_extract": "zhipu",
    "layer2_narrative": "deepseek",
    "layer3": "deepseek",
    "layer5_chart_narrative": "tongyi",
}


def get_client(
    provider: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    max_retries: int = 5,
    timeout: int = 120,
) -> LLMClient:
    """
    创建LLM客户端实例

    Args:
        provider: 提供商名称 (zhipu/glm/deepseek/tongyi/qwen/moonshot/openai)
        api_key: API密钥
        model: 模型名称
        base_url: 自定义API端点
        max_retries: 最大重试次数
        timeout: 请求超时(秒)

    Returns:
        LLMClient子类实例

    Raises:
        ValueError: 不支持的provider
    """
    provider_lower = provider.lower()

    if provider_lower not in PROVIDER_MAP:
        supported = ", ".join(sorted(PROVIDER_MAP.keys()))
        raise ValueError(
            f"不支持的LLM提供商 '{provider}'。支持: {supported}"
        )

    adapter_class = PROVIDER_MAP[provider_lower]

    # OpenAI兼容提供商可以传provider用于自动推断base_url
    if adapter_class == OpenAICompatClient:
        return OpenAICompatClient(
            api_key=api_key,
            model=model,
            base_url=base_url,
            provider=provider_lower,
            max_retries=max_retries,
            timeout=timeout,
        )

    # ZhipuClient等专用adapter
    kwargs = {
        "api_key": api_key,
        "max_retries": max_retries,
        "timeout": timeout,
    }
    if model:
        kwargs["model"] = model

    return adapter_class(**kwargs)


def get_client_for_stage(
    stage_name: str,
    api_key: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs,
) -> LLMClient:
    """
    根据Pipeline阶段创建对应的LLM客户端

    使用STAGE_PROVIDER_MAP确定默认provider。

    Args:
        stage_name: 阶段名 (layer2_extract/layer2_narrative/layer3/layer5_chart_narrative)
        api_key: API密钥
        model: 可选覆盖模型名
        base_url: 可选覆盖API端点

    Returns:
        LLMClient实例
    """
    if stage_name not in STAGE_PROVIDER_MAP:
        valid = ", ".join(STAGE_PROVIDER_MAP.keys())
        raise ValueError(
            f"未知Pipeline阶段 '{stage_name}'。支持: {valid}"
        )

    provider = STAGE_PROVIDER_MAP[stage_name]
    return get_client(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        **kwargs,
    )
