"""
Pipeline stage API routes — /api/task/*
"""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Response, Body, Depends
from pydantic import BaseModel

from storage import get_store
from api.auth import get_current_user
from api.deps import _get_user_task, MAX_CONCURRENT_PER_USER
from pipeline.orchestrator import Orchestrator as PipelineController

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/task", tags=["pipeline"])


# ============================================================
# Request Models
# ============================================================

class RerunPageRequest(BaseModel):
    user_feedback: str = ""


class SupplementRequest(BaseModel):
    """补充数据请求"""
    stage: str  # "outline" or "content"
    page_number: Optional[int] = None  # None=全局, 数字=特定页
    text_data: str = ""
    file_path: str = ""


# ============================================================
# Endpoints
# ============================================================

@router.get("/{task_id}/stages")
async def get_pipeline_stages(task_id: str, current_user: dict = Depends(get_current_user)):
    """获取任务所有Pipeline阶段的状态和结果"""
    store = get_store()
    task = _get_user_task(store, task_id, current_user["user_id"])

    stages = store.get_stages(task_id)
    return {
        "task_id": task_id,
        "task_status": task["status"],
        "stages": stages
    }


@router.get("/{task_id}/stage/{stage}")
async def get_pipeline_stage(task_id: str, stage: str, response: Response, current_user: dict = Depends(get_current_user)):
    """获取单个阶段详情（响应头含 ETag: "v{generation}"，供乐观锁使用）"""
    store = get_store()
    _get_user_task(store, task_id, current_user["user_id"])  # ownership check
    stage_data = store.get_stage(task_id, stage)
    if not stage_data:
        raise HTTPException(status_code=404, detail="阶段不存在")
    generation = stage_data.get("generation", 0)
    response.headers["ETag"] = f'"v{generation}"'
    return stage_data


@router.put("/{task_id}/stage/{stage}")
async def update_pipeline_stage(task_id: str, stage: str, request: Request, body: dict = None, current_user: dict = Depends(get_current_user)):
    """
    修改阶段结果（用户编辑后保存）

    支持乐观锁：携带 If-Match: "v{generation}" 头时做条件写入，版本冲突返回 412。
    不携带 If-Match 时直接覆盖（向后兼容）。
    保存后会自动重置该阶段后续阶段的状态。
    """
    store = get_store()
    _get_user_task(store, task_id, current_user["user_id"])  # ownership check
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


@router.post("/{task_id}/resume")
async def resume_pipeline(
    task_id: str,
    from_stage: str = "",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user),
):
    """
    从指定阶段恢复执行Pipeline

    如果不指定from_stage，从第一个pending阶段开始
    """
    store = get_store()
    task = _get_user_task(store, task_id, current_user["user_id"])

    if task["status"] not in ("checkpoint", "completed", "failed"):
        raise HTTPException(status_code=400, detail=f"任务状态为 {task['status']}，无法恢复")

    if from_stage:
        # 只重置下游阶段，不重置 from_stage 本身，不启动后台重跑
        # 用户回到大纲编辑时，大纲数据应保留，等用户编辑完点 confirm 再跑
        from storage import PIPELINE_STAGES
        from_idx = PIPELINE_STAGES.index(from_stage) if from_stage in PIPELINE_STAGES else -1
        downstream = PIPELINE_STAGES[from_idx + 1:] if from_idx >= 0 else []
        if downstream:
            store.reset_stages_list(task_id, downstream)
        return {
            "task_id": task_id,
            "message": f"下游阶段已重置",
            "status_url": f"/api/status/{task_id}"
        }
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


@router.post("/{task_id}/confirm")
async def confirm_checkpoint(
    task_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user),
):
    """确认当前检查点，继续执行到下一个检查点或完成"""
    store = get_store()
    task = _get_user_task(store, task_id, current_user["user_id"])

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


@router.post("/{task_id}/supplement")
async def add_supplemental_data(task_id: str, body: SupplementRequest, current_user: dict = Depends(get_current_user)):
    """
    添加补充数据

    在检查点等待时，用户可以补充额外信息，系统自动做微型分析。
    补充数据会在后续阶段（outline或content）被合并使用。
    """
    store = get_store()
    task = _get_user_task(store, task_id, current_user["user_id"])

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


@router.post("/{task_id}/rerun-page/{page_number}")
async def rerun_single_page(
    task_id: str,
    page_number: int,
    req: RerunPageRequest = Body(default_factory=RerunPageRequest),
    current_user: dict = Depends(get_current_user),
):
    """
    单页重跑：只重新生成指定页的内容。

    前提：content阶段已完成。
    可选 body: {"user_feedback": "告诉AI需要改进的方向"}
    """
    store = get_store()
    task = _get_user_task(store, task_id, current_user["user_id"])

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


@router.delete("/{task_id}")
async def delete_task(task_id: str, current_user: dict = Depends(get_current_user)):
    """删除任务记录"""
    store = get_store()
    task = _get_user_task(store, task_id, current_user["user_id"])

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


@router.get("/{task_id}/cost")
async def get_task_cost(task_id: str, current_user: dict = Depends(get_current_user)):
    """返回任务的 LLM token 消耗与预估成本"""
    from api.cost_tracker import aggregate_task_cost

    store = get_store()
    _get_user_task(store, task_id, current_user["user_id"])  # ownership check

    stages = store.get_stages(task_id)
    return aggregate_task_cost(stages)
