"""
FastAPI 主应用
PPT Agent 后端 API 服务
"""

import sys
import os
import uuid
import asyncio
import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict

# 让 pipeline/agents 的 INFO 日志输出到 docker logs
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载 .env 环境变量
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, Request, Response, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from models import RawContent, Narrative, PresentationSpec
from llm_client import GLMClient
from pipeline.layer1_input import InputRouter
from pipeline.layer4_visual import VisualDesigner
from pipeline.layer5_chart import ChartGenerator
from pipeline.layer6_output import PPTBuilder
from storage import get_store
from pipeline.orchestrator import Orchestrator as PipelineController
from api.auth import router as auth_router

# ============================================================
# FastAPI 应用初始化
# ============================================================

app = FastAPI(
    title="PPT Agent API",
    description="专业PPT自动生成系统 - 四大咨询级别",
    version="0.1.0"
)

# 跨域配置（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册认证路由（公开端点，不需要认证）
app.include_router(auth_router)

# ============================================================
# 数据模型
# ============================================================

class GenerateRequest(BaseModel):
    """生成PPT请求"""
    title: str = "未命名演示文稿"
    content: str  # 原始文本内容
    target_audience: str = "管理层"
    scenario: str = ""  # 汇报场景
    language: str = "zh"  # zh 或 en


class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: int  # 0-100
    current_step: str
    message: str
    created_at: str
    output_file: Optional[str] = None
    error: Optional[str] = None


# ============================================================
# 全局状态
# ============================================================

# 输出目录
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# LLM客户端（懒加载）
llm_client = None
llm_api_key = os.getenv("GLM_API_KEY", "")
llm_model = "glm-5.1"

# ============================================================
# 幂等性缓存（防止网络重试创建重复任务）
# key → (task_id, expires_at)，最大1000条，超出时清理过期项
# ============================================================

_idempotency_cache: Dict[str, Tuple[str, datetime]] = {}
_idempotency_lock = threading.Lock()


def _check_idempotency(key: str) -> Optional[str]:
    """返回已有 task_id（未过期），否则 None。"""
    if not key:
        return None
    with _idempotency_lock:
        entry = _idempotency_cache.get(key)
        if entry:
            task_id, expires_at = entry
            if datetime.now() < expires_at:
                return task_id
            del _idempotency_cache[key]
    return None


def _register_idempotency(key: str, task_id: str, ttl_hours: int = 24) -> None:
    """注册 key → task_id，TTL 24h；超过1000条时清理过期项。"""
    if not key:
        return
    with _idempotency_lock:
        _idempotency_cache[key] = (task_id, datetime.now() + timedelta(hours=ttl_hours))
        if len(_idempotency_cache) > 1000:
            now = datetime.now()
            expired = [k for k, (_, exp) in _idempotency_cache.items() if now > exp]
            for k in expired:
                del _idempotency_cache[k]


def get_llm_client():
    """获取LLM客户端（懒加载）"""
    global llm_client
    if llm_client is None:
        if not llm_api_key:
            raise ValueError("请先在设置中配置API Key")
        llm_client = GLMClient(api_key=llm_api_key, model=llm_model)
    return llm_client


# ============================================================
# SSE 进度推送
# ============================================================

def _task_snapshot(task: dict) -> dict:
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task["progress"],
        "current_step": task["current_step"],
        "message": task["message"],
        "output_file": task.get("output_file"),
        "error": task.get("error"),
    }


async def send_progress(task_id: str):
    """SSE推送任务进度（事件驱动，update_task 后立即推送，无固定轮询）"""
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        return

    async def event_generator():
        q = store.subscribe(task_id)
        try:
            # 立即推送当前状态
            task = store.get_task(task_id)
            if not task:
                return
            yield f"data: {json.dumps(_task_snapshot(task), ensure_ascii=False)}\n\n"
            if task["status"] in ("completed", "failed", "checkpoint"):
                return

            while True:
                try:
                    # 等待 update_task 信号，15s 超时做心跳防止连接断开
                    await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    pass  # 心跳：重读一次状态

                task = store.get_task(task_id)
                if not task:
                    break
                yield f"data: {json.dumps(_task_snapshot(task), ensure_ascii=False)}\n\n"
                if task["status"] in ("completed", "failed", "checkpoint"):
                    break
        finally:
            store.unsubscribe(task_id)

    return event_generator()


# ============================================================
# 核心生成流程
# ============================================================

async def generate_ppt_pipeline(task_id: str):
    """
    Pipeline入口：执行到第一个检查点暂停
    """
    controller = PipelineController()
    await controller.run_full(task_id)


# ============================================================
# API 端点
# ============================================================

@app.get("/")
async def root():
    """API根端点"""
    return {
        "name": "PPT Agent API",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "generate": "/api/generate",
            "generate_file": "/api/generate/file",
            "status": "/api/status/{task_id}",
            "download": "/api/download/{task_id}",
            "history": "/api/history",
            "config": "/api/config"
        }
    }


class ConfigRequest(BaseModel):
    """配置请求（向后兼容旧端点）"""
    api_key: str
    model: str = "glm-5.1"


@app.get("/api/config/models")
async def get_model_config():
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
    for stage in [masked.analyze, masked.outline, masked.content, masked.build]:
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


@app.put("/api/config/models")
async def update_model_config(body: Dict):
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

    if body.get("config_mode") == "universal":
        # ── 通用模式：1个配置应用到4个stage ──
        universal = {
            "provider": body.get("universal_provider", "deepseek"),
            "model": body.get("universal_model", "deepseek-chat"),
            "api_key": body.get("universal_api_key", ""),
            "base_url": body.get("universal_base_url"),
        }
        for stage_name in ["analyze", "outline", "content", "build"]:
            stage_config = StageModelConfig(**universal)
            if stage_config.api_key:
                encrypted = encrypt_api_key(stage_config.api_key)
                store.save_api_key("default", stage_config.provider, encrypted)
                stage_config.api_key = ""
                stage_config.has_api_key = True
            pmc.set_stage_config(stage_name, stage_config)
            updated_stages.append(stage_name)
        store.save_setting("default", "config_mode", "universal")
    else:
        # ── 分阶段模式（现有逻辑）──
        for stage_name in ["analyze", "outline", "content", "build"]:
            if stage_name in body and isinstance(body[stage_name], dict):
                stage_data = body[stage_name]
                try:
                    stage_config = StageModelConfig(**stage_data)
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"阶段 {stage_name} 配置无效: {e}")

                if stage_config.api_key:
                    encrypted = encrypt_api_key(stage_config.api_key)
                    store.save_api_key("default", stage_config.provider, encrypted)
                    stage_config.api_key = ""
                    stage_config.has_api_key = True

                pmc.set_stage_config(stage_name, stage_config)
                updated_stages.append(stage_name)
        store.save_setting("default", "config_mode", "advanced")

    # 保存配置
    store.save_setting("default", "pipeline_model_config", pmc.model_dump_json())

    return {
        "message": f"模型配置已更新: {', '.join(updated_stages)}",
        "updated_stages": updated_stages,
    }


@app.post("/api/config")
async def update_config_legacy(config: ConfigRequest):
    """
    旧版配置端点（向后兼容）

    设置全局GLM API Key
    """
    global llm_api_key, llm_model, llm_client

    if not config.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key不能为空")

    llm_api_key = config.api_key.strip()
    llm_model = config.model.strip()
    llm_client = None

    return {
        "message": "配置已更新",
        "model": llm_model,
        "key_set": True
    }


@app.get("/api/config")
async def get_config_legacy():
    """旧版配置端点（向后兼容）"""
    return {
        "llm_configured": bool(llm_api_key),
        "model": llm_model,
        "key_masked": llm_api_key[:8] + "..." + llm_api_key[-4:] if len(llm_api_key) > 12 else ("已设置" if llm_api_key else "未设置")
    }


@app.post("/api/generate")
async def generate_ppt(
    raw_request: Request,
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
):
    """
    启动PPT生成任务（异步）

    携带 Idempotency-Key 头时，重复请求返回已有任务而不重复创建。
    返回task_id，客户端通过SSE监听进度。
    """
    idempotency_key = raw_request.headers.get("Idempotency-Key", "").strip()
    existing = _check_idempotency(idempotency_key)
    if existing:
        return {
            "task_id": existing,
            "status": "pending",
            "message": "幂等请求，返回已有任务",
            "status_url": f"/api/status/{existing}",
        }

    store = get_store()
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    store.create_task(
        task_id=task_id,
        title=request.title,
        content=request.content,
        target_audience=request.target_audience,
        scenario=request.scenario,
        language=request.language,
        created_at=now,
    )
    _register_idempotency(idempotency_key, task_id)

    # 后台执行生成流程
    background_tasks.add_task(generate_ppt_pipeline, task_id)

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "任务已创建，正在后台处理",
        "status_url": f"/api/status/{task_id}",
    }


@app.post("/api/generate/file")
async def generate_ppt_from_file(
    raw_request: Request,
    file: UploadFile = File(...),
    title: str = Form("未命名演示文稿"),
    target_audience: str = Form("管理层"),
    scenario: str = Form(""),
    language: str = Form(""),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    通过文件上传启动PPT生成任务

    携带 Idempotency-Key 头时，重复请求返回已有任务而不重复创建。
    支持 .docx, .xlsx, .csv, .pptx, .txt, .md 格式。
    """
    idempotency_key = raw_request.headers.get("Idempotency-Key", "").strip()
    existing = _check_idempotency(idempotency_key)
    if existing:
        return {
            "task_id": existing,
            "status": "pending",
            "message": "幂等请求，返回已有任务",
            "status_url": f"/api/status/{existing}",
        }

    # 验证文件大小（50MB）
    MAX_SIZE = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="文件过大，请上传50MB以内的文件")

    # 验证文件扩展名
    ext = Path(file.filename).suffix.lower()
    supported = [".docx", ".xlsx", ".csv", ".pptx", ".txt", ".md"]
    if ext not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 '{ext}'，支持: {', '.join(supported)}"
        )

    # 保存文件
    task_id = str(uuid.uuid4())
    upload_dir = Path(f"storage/uploads/{task_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    with open(file_path, "wb") as f:
        f.write(content)

    # 创建任务
    store = get_store()
    now = datetime.now().isoformat()
    store.create_task(
        task_id=task_id,
        title=title if title else Path(file.filename).stem,
        content="",
        target_audience=target_audience,
        scenario=scenario,
        language=language or "zh",
        file_path=str(file_path),
        created_at=now,
    )

    _register_idempotency(idempotency_key, task_id)

    # 后台执行
    background_tasks.add_task(generate_ppt_pipeline, task_id)

    return {
        "task_id": task_id,
        "status": "pending",
        "message": f"文件已上传，正在处理: {file.filename}",
        "status_url": f"/api/status/{task_id}",
    }


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """获取任务状态（SSE实时推送）"""
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 返回SSE流
    return StreamingResponse(
        await send_progress(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/status/{task_id}/json")
async def get_status_json(task_id: str):
    """获取任务状态（JSON格式，一次性返回）"""
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task["progress"],
        "current_step": task["current_step"],
        "message": task["message"],
        "output_file": task.get("output_file"),
        "error": task.get("error"),
        "narrative": task.get("narrative"),
        "slides": task.get("slides")
    }


@app.get("/api/download/{task_id}")
async def download_ppt(task_id: str):
    """下载生成的PPT文件"""
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="PPT尚未生成完成")

    output_file = task.get("output_file")
    if not output_file or not Path(output_file).exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=output_file,
        filename=Path(output_file).name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )


@app.get("/api/history")
async def get_history(limit: int = 20):
    """获取生成历史"""
    store = get_store()
    recent = store.get_history(limit)
    total = store.count_all()

    return {
        "total": total,
        "items": [
            {
                "task_id": t["task_id"],
                "title": t["title"],
                "status": t["status"],
                "created_at": t["created_at"],
                "output_file": t.get("output_file")
            }
            for t in recent
        ]
    }


# ============================================================
# Pipeline阶段API
# ============================================================

@app.get("/api/task/{task_id}/stages")
async def get_pipeline_stages(task_id: str):
    """获取任务所有Pipeline阶段的状态和结果"""
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    stages = store.get_stages(task_id)
    return {
        "task_id": task_id,
        "task_status": task["status"],
        "stages": stages
    }


@app.get("/api/task/{task_id}/stage/{stage}")
async def get_pipeline_stage(task_id: str, stage: str, response: Response):
    """获取单个阶段详情（响应头含 ETag: "v{generation}"，供乐观锁使用）"""
    store = get_store()
    stage_data = store.get_stage(task_id, stage)
    if not stage_data:
        raise HTTPException(status_code=404, detail="阶段不存在")
    generation = stage_data.get("generation", 0)
    response.headers["ETag"] = f'"v{generation}"'
    return stage_data


@app.put("/api/task/{task_id}/stage/{stage}")
async def update_pipeline_stage(task_id: str, stage: str, request: Request, body: Dict = None):
    """
    修改阶段结果（用户编辑后保存）

    支持乐观锁：携带 If-Match: "v{generation}" 头时做条件写入，版本冲突返回 412。
    不携带 If-Match 时直接覆盖（向后兼容）。
    保存后会自动重置该阶段后续阶段的状态。
    """
    store = get_store()
    if not body:
        raise HTTPException(status_code=400, detail="请求体不能为空")

    stage_data = store.get_stage(task_id, stage)
    if not stage_data:
        raise HTTPException(status_code=404, detail="阶段不存在")

    # 乐观锁：If-Match 头存在时做条件写入
    if_match = request.headers.get("If-Match", "").strip()
    if if_match:
        gen_str = if_match.strip('"').lstrip("v")
        try:
            expected_gen = int(gen_str)
        except ValueError:
            raise HTTPException(status_code=400, detail='If-Match 格式错误，应为 "v{number}"')

        success, current_gen = store.check_and_save_stage_result(task_id, stage, expected_gen, body)
        if not success:
            raise HTTPException(
                status_code=412,
                detail=f"资源已被修改（当前 generation={current_gen}），请刷新后重试",
                headers={"ETag": f'"v{current_gen}"'},
            )
    else:
        store.save_stage_result(task_id, stage, body)

    # 重置后续阶段（输入已变，需要重跑）
    from storage import PIPELINE_STAGES
    idx = PIPELINE_STAGES.index(stage) if stage in PIPELINE_STAGES else -1
    if idx >= 0 and idx < len(PIPELINE_STAGES) - 1:
        store.reset_stages_from(task_id, PIPELINE_STAGES[idx + 1])

    return {"message": f"阶段 {stage} 已更新，后续阶段已重置"}


@app.post("/api/task/{task_id}/resume")
async def resume_pipeline(
    task_id: str,
    from_stage: str = "",
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    从指定阶段恢复执行Pipeline

    如果不指定from_stage，从第一个pending阶段开始
    """
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] not in ("checkpoint", "completed", "failed"):
        raise HTTPException(status_code=400, detail=f"任务状态为 {task['status']}，无法恢复")

    if from_stage:
        # 重置从指定阶段开始
        store.reset_stages_from(task_id, from_stage)
    else:
        # 找到第一个pending的阶段
        stages = store.get_stages(task_id)
        for s in stages:
            if s["status"] != "completed":
                from_stage = s["stage"]
                break
        if not from_stage:
            raise HTTPException(status_code=400, detail="所有阶段已完成")

    async def do_resume():
        controller = PipelineController()
        await controller.resume_from(task_id, from_stage)

    background_tasks.add_task(do_resume)

    return {
        "task_id": task_id,
        "message": f"从阶段 {from_stage} 恢复执行",
        "status_url": f"/api/status/{task_id}"
    }


@app.post("/api/task/{task_id}/confirm")
async def confirm_checkpoint(
    task_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """确认当前检查点，继续执行到下一个检查点或完成"""
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] != "checkpoint":
        raise HTTPException(status_code=400, detail="任务未在检查点暂停，无法确认")

    async def do_confirm():
        controller = PipelineController()
        await controller.confirm_checkpoint(task_id)

    background_tasks.add_task(do_confirm)

    return {
        "task_id": task_id,
        "message": "检查点已确认，继续执行",
        "status_url": f"/api/status/{task_id}"
    }


class RerunPageRequest(BaseModel):
    user_feedback: str = ""


class SupplementRequest(BaseModel):
    """补充数据请求"""
    stage: str  # "outline" or "content"
    page_number: Optional[int] = None  # None=全局, 数字=特定页
    text_data: str = ""
    file_path: str = ""


@app.post("/api/task/{task_id}/supplement")
async def add_supplemental_data(task_id: str, body: SupplementRequest):
    """
    添加补充数据

    在检查点等待时，用户可以补充额外信息，系统自动做微型分析。
    补充数据会在后续阶段（outline或content）被合并使用。
    """
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if body.stage not in ("outline", "content"):
        raise HTTPException(status_code=400, detail="stage必须是outline或content")

    data_id = str(uuid.uuid4())

    store.save_supplemental_data(
        task_id=task_id,
        data_id=data_id,
        stage=body.stage,
        page_number=body.page_number,
        text_data=body.text_data,
        file_path=body.file_path,
    )

    return {
        "data_id": data_id,
        "message": "补充数据已保存",
    }


@app.post("/api/task/{task_id}/rerun-page/{page_number}")
async def rerun_single_page(
    task_id: str,
    page_number: int,
    req: RerunPageRequest = Body(default_factory=RerunPageRequest),
):
    """
    单页重跑：只重新生成指定页的内容。

    前提：content阶段已完成。
    可选 body: {"user_feedback": "告诉AI需要改进的方向"}
    """
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    content_stage = store.get_stage(task_id, "content")
    if not content_stage or content_stage["status"] != "completed":
        raise HTTPException(status_code=400, detail="content阶段未完成，无法单页重跑")

    try:
        controller = PipelineController()
        await controller.rerun_page(task_id, page_number, user_feedback=req.user_feedback)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=f"重跑失败：{e}")
    except Exception as e:
        logger.exception("rerun_page 异常")
        raise HTTPException(status_code=500, detail=f"内部错误：{type(e).__name__}: {e}")

    # Return updated slide data for frontend to refresh
    updated_content = store.get_stage_result(task_id, "content") or {}
    updated_slides = updated_content.get("slides", [])
    updated_slide = next((s for s in updated_slides if s.get("page_number") == page_number), None)

    return {
        "task_id": task_id,
        "page_number": page_number,
        "message": f"第{page_number}页内容已重新生成",
        "slide": updated_slide,
    }


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """删除任务记录"""
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 删除生成的PPT文件
    output_file = task.get("output_file")
    if output_file and Path(output_file).exists():
        Path(output_file).unlink()

    # 删除上传文件目录
    file_path = task.get("file_path")
    if file_path:
        upload_dir = Path(file_path).parent
        if upload_dir.exists():
            import shutil
            shutil.rmtree(upload_dir, ignore_errors=True)

    # 删除数据库记录
    store.delete_task(task_id)

    return {"message": "任务已删除"}


# ============================================================
# 健康检查
# ============================================================

@app.get("/api/health")
async def health_check():
    """健康检查"""
    store = get_store()
    return {
        "status": "healthy",
        "llm_configured": bool(os.getenv("GLM_API_KEY")),
        "output_dir_exists": OUTPUT_DIR.exists(),
        "active_tasks": store.count_by_status("processing"),
        "total_tasks": store.count_all(),
    }


# ============================================================
# 启动事件
# ============================================================

@app.on_event("startup")
async def startup():
    """应用启动时初始化存储，并注入事件循环引用（SSE事件驱动所需）"""
    store = get_store()
    store.set_event_loop(asyncio.get_running_loop())
    print("📦 存储层已初始化 (PostgreSQL)")


# ============================================================
# 启动脚本
# ============================================================

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("  PPT Agent API Server")
    print("=" * 60)
    print(f"  访问地址: http://localhost:8000")
    print(f"  API文档: http://localhost:8000/docs")
    print(f"  健康检查: http://localhost:8000/api/health")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
