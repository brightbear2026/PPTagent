"""
Shared helpers, constants, and pipeline entry point.
Imported by main.py and all route modules — no circular deps.
"""

import os
import uuid
import asyncio
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from fastapi import HTTPException
from pydantic import BaseModel

from storage import get_store
from pipeline.orchestrator import Orchestrator as PipelineController


# ============================================================
# 数据模型（shared）
# ============================================================

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

# ============================================================
# 并发限制常量
# ============================================================

MAX_CONCURRENT_PER_USER = int(os.environ.get("MAX_CONCURRENT_PER_USER", "2"))
MAX_CONCURRENT_GLOBAL = int(os.environ.get("MAX_CONCURRENT_TASKS", "10"))

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


# ============================================================
# SSE 进度推送（shared helpers）
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


def _get_user_task(store, task_id: str, user_id: str) -> dict:
    """Fetch a task belonging to the current user, or raise 404."""
    task = store.get_task(task_id)
    if not task or task.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


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
    Pipeline入口：执行到第一个检查点暂停。
    顶层 try/except 防止 orchestrator 未捕获的异常导致 task 永远卡在 pending。
    """
    try:
        controller = PipelineController()
        await controller.run_full(task_id)
    except Exception as e:
        logger.exception("Pipeline unhandled error for task %s", task_id)
        try:
            store = get_store()
            store.update_task(task_id, status="failed", error=f"内部错误: {e}")
        except Exception:
            logger.exception("Failed to mark task %s as failed", task_id)
