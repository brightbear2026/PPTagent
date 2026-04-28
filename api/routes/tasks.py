"""
Task API routes — generate, status, download, history
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form, Request, Depends
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from storage import get_store
from api.auth import get_current_user, decode_token
from api.deps import (
    _check_idempotency,
    _register_idempotency,
    _get_user_task,
    send_progress,
    generate_ppt_pipeline,
    MAX_CONCURRENT_PER_USER,
    MAX_CONCURRENT_GLOBAL,
)

router = APIRouter(tags=["tasks"])


# ============================================================
# Request Models
# ============================================================

class GenerateRequest(BaseModel):
    """生成PPT请求"""
    title: str = "未命名演示文稿"
    content: str  # 原始文本内容
    target_audience: str = "管理层"
    scenario: str = ""  # 汇报场景
    language: str = "zh"  # zh 或 en


# ============================================================
# Endpoints
# ============================================================

@router.post("/api/generate")
async def generate_ppt(
    raw_request: Request,
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    启动PPT生成任务（异步）

    携带 Idempotency-Key 头时，重复请求返回已有任务而不重复创建。
    返回task_id，客户端通过SSE监听进度。
    """
    store = get_store()

    # Per-user concurrent task limit
    user_running = store.get_running_task_count(user_id=current_user["user_id"])
    if user_running >= MAX_CONCURRENT_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"您当前有 {user_running} 个生成任务在进行，完成后可发起新任务",
        )

    # Global concurrent task limit
    global_running = store.get_running_task_count()
    if global_running >= MAX_CONCURRENT_GLOBAL:
        raise HTTPException(
            status_code=429,
            detail="系统繁忙，请稍后再试",
        )

    idempotency_key = raw_request.headers.get("Idempotency-Key", "").strip()
    existing = _check_idempotency(idempotency_key)
    if existing:
        return {
            "task_id": existing,
            "status": "pending",
            "message": "幂等请求，返回已有任务",
            "status_url": f"/api/status/{existing}",
        }

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
        user_id=current_user["user_id"],
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


@router.post("/api/generate/file")
async def generate_ppt_from_file(
    raw_request: Request,
    file: UploadFile = File(...),
    title: str = Form("未命名演示文稿"),
    target_audience: str = Form("管理层"),
    scenario: str = Form(""),
    language: str = Form(""),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user),
):
    """
    通过文件上传启动PPT生成任务

    携带 Idempotency-Key 头时，重复请求返回已有任务而不重复创建。
    支持 .docx, .xlsx, .csv, .pptx, .txt, .md 格式。
    """
    store = get_store()

    # Per-user concurrent task limit
    user_running = store.get_running_task_count(user_id=current_user["user_id"])
    if user_running >= MAX_CONCURRENT_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"您当前有 {user_running} 个生成任务在进行，完成后可发起新任务",
        )

    # Global concurrent task limit
    global_running = store.get_running_task_count()
    if global_running >= MAX_CONCURRENT_GLOBAL:
        raise HTTPException(
            status_code=429,
            detail="系统繁忙，请稍后再试",
        )

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

    # 文件名消毒（防路径穿越）
    safe_name = os.path.basename(file.filename)
    if safe_name != file.filename or ".." in file.filename:
        raise HTTPException(status_code=400, detail="文件名包含非法字符")

    # 保存文件
    task_id = str(uuid.uuid4())
    upload_dir = Path(f"storage/uploads/{task_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / safe_name

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
        user_id=current_user["user_id"],
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


@router.get("/api/status/{task_id}")
async def get_status(task_id: str, token: Optional[str] = None):
    """获取任务状态（SSE实时推送，通过 query param 认证）"""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    store = get_store()
    task = _get_user_task(store, task_id, user_id)

    # 返回SSE流
    return StreamingResponse(
        await send_progress(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/api/status/{task_id}/json")
async def get_status_json(task_id: str, current_user: dict = Depends(get_current_user)):
    """获取任务状态（JSON格式，一次性返回）"""
    store = get_store()
    task = _get_user_task(store, task_id, current_user["user_id"])

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


@router.get("/api/download/{task_id}")
async def download_ppt(task_id: str, token: Optional[str] = None):
    """下载生成的PPT文件（支持 query param token 用于浏览器直接下载）"""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    store = get_store()
    task = _get_user_task(store, task_id, user_id)

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


@router.get("/api/history")
async def get_history(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """获取生成历史"""
    store = get_store()
    recent = store.get_history(limit, user_id=current_user["user_id"])
    total = store.count_by_user(current_user["user_id"])

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
