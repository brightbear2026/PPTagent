"""
Pipeline各阶段的模型配置
6阶段Pipeline中的LLM调用阶段：analyze, outline, content, design
render阶段为纯代码渲染，不需要LLM。
"""

from typing import Optional
from pydantic import BaseModel, Field


class StageModelConfig(BaseModel):
    """单个Pipeline阶段的LLM模型配置"""

    provider: str = Field(
        ...,
        description="LLM提供商: zhipu, deepseek, tongyi",
    )
    model: str = Field(
        ...,
        description="模型名称，如 glm-4-plus, deepseek-r1, qwen-max",
    )
    api_key: str = Field(
        default="",
        description="API密钥（存储时加密）",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="自定义API端点，用于OpenAI兼容提供商",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="采样温度",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=32768,
        description="最大生成token数",
    )
    has_api_key: bool = Field(
        default=False,
        description="是否已设置API Key（加密存储后标记为True）",
    )

    model_config = {"extra": "forbid"}


# 各阶段默认配置
STAGE_DEFAULTS: dict[str, StageModelConfig] = {
    "analyze": StageModelConfig(
        provider="zhipu",
        model="glm-4-plus",
        temperature=0.3,
        max_tokens=8192,
    ),
    "outline": StageModelConfig(
        provider="deepseek",
        model="deepseek-r1",
        temperature=0.4,
        max_tokens=4096,
        base_url="https://api.deepseek.com/v1",
    ),
    "content": StageModelConfig(
        provider="deepseek",
        model="deepseek-r1",
        temperature=0.4,
        max_tokens=4096,
        base_url="https://api.deepseek.com/v1",
    ),
    "design": StageModelConfig(
        provider="tongyi",
        model="qwen-max",
        temperature=0.5,
        max_tokens=4096,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
}


class PipelineModelConfig(BaseModel):
    """
    Pipeline全阶段模型配置
    4个LLM调用阶段各自独立配置：analyze, outline, content, design
    render阶段为纯代码，不需要LLM配置。
    """

    analyze: StageModelConfig = Field(
        default_factory=lambda: STAGE_DEFAULTS["analyze"].model_copy(),
    )
    outline: StageModelConfig = Field(
        default_factory=lambda: STAGE_DEFAULTS["outline"].model_copy(),
    )
    content: StageModelConfig = Field(
        default_factory=lambda: STAGE_DEFAULTS["content"].model_copy(),
    )
    design: StageModelConfig = Field(
        default_factory=lambda: STAGE_DEFAULTS["design"].model_copy(),
    )
    # build 保留为向后兼容别名（映射到 design）
    build: StageModelConfig = Field(
        default_factory=lambda: STAGE_DEFAULTS["design"].model_copy(),
    )

    model_config = {"extra": "forbid"}

    def get_stage_config(self, stage_name: str) -> StageModelConfig:
        """根据阶段名获取对应配置"""
        mapping = {
            "analyze": self.analyze,
            "outline": self.outline,
            "content": self.content,
            "design": self.design,
            "build": self.build,   # 向后兼容
        }
        if stage_name not in mapping:
            raise ValueError(
                f"未知阶段 '{stage_name}'，"
                f"支持: {', '.join(mapping.keys())}"
            )
        return mapping[stage_name]

    def set_stage_config(self, stage_name: str, config: StageModelConfig) -> None:
        """更新指定阶段的配置"""
        valid_stages = {"analyze", "outline", "content", "design", "build"}
        if stage_name not in valid_stages:
            raise ValueError(
                f"未知阶段 '{stage_name}'，"
                f"支持: {', '.join(valid_stages)}"
            )
        setattr(self, stage_name, config)

    def mask_api_keys(self) -> "PipelineModelConfig":
        """返回api_key被遮蔽的副本（用于API响应）"""
        masked = self.model_copy(deep=True)
        for stage in [masked.analyze, masked.outline, masked.content, masked.design, masked.build]:
            if stage.api_key:
                stage.api_key = stage.api_key[:8] + "****" + stage.api_key[-4:]
        return masked
