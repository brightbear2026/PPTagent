"""
FastAPI 主应用
PPT Agent 后端 API 服务
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载 .env 环境变量
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# 配置结构化日志
from api.logging_config import setup_logging
setup_logging()

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from storage import get_store
from api.auth import router as auth_router
from api.auth import get_current_user
from api.deps import OUTPUT_DIR, MAX_CONCURRENT_PER_USER

# ============================================================
# FastAPI 应用初始化
# ============================================================

app = FastAPI(
    title="PPT Agent API",
    description="专业PPT自动生成系统 - 四大咨询级别",
    version="0.1.0"
)

# 跨域配置（从环境变量读取白名单）
_cors_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册认证路由（公开端点，不需要认证）
app.include_router(auth_router)

# 注册业务路由
from api.routes.settings import router as settings_router
from api.routes.tasks import router as tasks_router
from api.routes.pipeline import router as pipeline_router

app.include_router(settings_router)
app.include_router(tasks_router)
app.include_router(pipeline_router)


# ============================================================
# 根端点
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


# ============================================================
# 用户配额
# ============================================================

@app.get("/api/user/quota")
async def get_user_quota(current_user: dict = Depends(get_current_user)):
    """返回当前用户的并发任务配额信息"""
    store = get_store()
    running_count = store.get_running_task_count(user_id=current_user["user_id"])
    return {
        "running_count": running_count,
        "max_concurrent": MAX_CONCURRENT_PER_USER,
        "can_create": running_count < MAX_CONCURRENT_PER_USER,
    }


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
