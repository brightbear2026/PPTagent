"""
Settings API routes — /api/config/models
"""

from typing import Dict
from fastapi import APIRouter, HTTPException, Depends

from storage import get_store
from api.auth import get_current_user

router = APIRouter(prefix="/api/config", tags=["settings"])


@router.get("/models")
async def get_model_config(current_user: dict = Depends(get_current_user)):
    """
    获取Pipeline各阶段模型配置

    返回4个LLM调用阶段(analyze/outline/content/build)的provider/model/api_key状态
    """
    store = get_store()
    config = store.get_pipeline_model_config("default")

    # 遮蔽API Key，并检查api_keys表补充has_api_key标记
    from models.model_config import PipelineModelConfig
    pmc = PipelineModelConfig(**config)
    masked = pmc.mask_api_keys()

    # 对每个阶段，检查加密表是否有对应的key
    for stage in [masked.analyze, masked.outline, masked.content, masked.design, masked.build]:
        if not stage.has_api_key:
            encrypted = store.get_api_key("default", stage.provider)
            if encrypted:
                stage.has_api_key = True

    config_mode = store.get_setting("default", "config_mode") or "advanced"

    return {
        "config": {**masked.model_dump(), "config_mode": config_mode},
        "available_providers": list({
            "zhipu": "智谱GLM",
            "deepseek": "DeepSeek",
            "tongyi": "通义千问",
            "qwen": "通义千问(Qwen)",
            "moonshot": "Moonshot",
        }.keys()),
    }


@router.put("/models")
async def update_model_config(body: Dict, current_user: dict = Depends(get_current_user)):
    """
    更新Pipeline各阶段模型配置

    请求体格式：
    {
        "outline": {"provider": "deepseek", "model": "deepseek-r1", "api_key": "xxx"},
        "content": {"provider": "zhipu", "model": "glm-4-plus", "api_key": "xxx"},
        ...
    }
    """
    from models.model_config import PipelineModelConfig, StageModelConfig
    from storage.encryption import encrypt_api_key, decrypt_api_key

    store = get_store()

    # 获取当前配置
    config_json = store.get_setting("default", "pipeline_model_config")
    if config_json:
        try:
            pmc = PipelineModelConfig.model_validate_json(config_json)
        except Exception:
            pmc = PipelineModelConfig()
    else:
        pmc = PipelineModelConfig()

    updated_stages = []

    # Accept both "design" and "build" keys from frontend, normalize to "design"
    STAGE_MAP = {"analyze": "analyze", "outline": "outline", "content": "content", "design": "design", "build": "design"}

    if body.get("config_mode") == "universal":
        # ── 通用模式：1个配置应用到4个stage ──
        universal = {
            "provider": body.get("universal_provider", "deepseek"),
            "model": body.get("universal_model", "deepseek-chat"),
            "api_key": body.get("universal_api_key", ""),
            "base_url": body.get("universal_base_url"),
        }
        for stage_name in ["analyze", "outline", "content", "design"]:
            stage_config = StageModelConfig(**universal)
            if stage_config.api_key:
                encrypted = encrypt_api_key(stage_config.api_key)
                store.save_api_key("default", stage_config.provider, encrypted)
                stage_config.api_key = ""
                stage_config.has_api_key = True
            pmc.set_stage_config(stage_name, stage_config)
            updated_stages.append(stage_name)
        # Also update build alias
        pmc.build = pmc.design.model_copy()
        store.save_setting("default", "config_mode", "universal")
    else:
        # ── 分阶段模式 ──
        for body_key, stage_name in STAGE_MAP.items():
            if body_key in body and isinstance(body[body_key], dict):
                stage_data = body[body_key]
                try:
                    stage_config = StageModelConfig(**stage_data)
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"阶段 {stage_name} 配置无效: {e}")

                if stage_config.api_key:
                    encrypted = encrypt_api_key(stage_config.api_key)
                    store.save_api_key("default", stage_config.provider, encrypted)
                    stage_config.api_key = ""
                    stage_config.has_api_key = True
                else:
                    # No new key provided — preserve existing has_api_key if encrypted key exists
                    encrypted = store.get_api_key("default", stage_config.provider)
                    if encrypted:
                        stage_config.has_api_key = True

                pmc.set_stage_config(stage_name, stage_config)
                updated_stages.append(stage_name)
        # Sync build alias
        pmc.build = pmc.design.model_copy()
        store.save_setting("default", "config_mode", "advanced")

    # 保存配置
    store.save_setting("default", "pipeline_model_config", pmc.model_dump_json())

    return {
        "message": f"模型配置已更新: {', '.join(updated_stages)}",
        "updated_stages": updated_stages,
    }
