"""
任务存储 - PostgreSQL实现
持久化任务信息，支持服务重启后恢复
支持Pipeline阶段级别的存储和查询

通过 DATABASE_URL 环境变量连接 PostgreSQL
使用 psycopg2 + RealDictCursor
"""

import asyncio
import json
import os
import threading
import time
import psycopg2
import psycopg2.extras
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# 默认连接URL
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://pptagent:pptagent_local@localhost:5432/pptagent"
)

# Pipeline阶段定义（6阶段 + 2检查点）
PIPELINE_STAGES = [
    "parse",             # 输入解析（静默）
    "analyze",           # 数据分析（静默）
    "outline",           # 大纲生成（检查点1）
    "content",           # 内容填充（检查点2）
    "design",            # 视觉设计+图表生成（静默，LLM辅助）
    "render",            # PPT渲染+布局验证（静默，纯代码）
]


class TaskStore:
    """任务持久化存储（PostgreSQL）"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or DATABASE_URL
        # in-memory pub-sub for SSE (not persisted, per-process)
        self._queues: Dict[str, asyncio.Queue] = {}
        self._queue_lock = threading.Lock()
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._init_db()

    # ── SSE 事件推送 ──

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """由 FastAPI startup 调用，保存主事件循环引用，用于跨线程推送。"""
        self._event_loop = loop

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """SSE handler 调用：注册并返回该 task 的更新队列。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._queue_lock:
            self._queues[task_id] = q
        return q

    def unsubscribe(self, task_id: str) -> None:
        """SSE 连接关闭时取消订阅。"""
        with self._queue_lock:
            self._queues.pop(task_id, None)

    def _notify(self, task_id: str) -> None:
        """update_task 后通知订阅队列（线程安全，从 worker thread 调用）。"""
        with self._queue_lock:
            q = self._queues.get(task_id)
        if q is None or self._event_loop is None:
            return
        try:
            self._event_loop.call_soon_threadsafe(q.put_nowait, True)
        except Exception:
            pass

    @contextmanager
    def _connect(self):
        """获取数据库连接（RealDictCursor 自动返回字典）"""
        conn = psycopg2.connect(
            self.database_url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        conn.autocommit = False
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self, retries=5, delay=2):
        """Run Alembic migrations to initialize / upgrade the database schema."""
        import logging as _logging
        import os

        _log = _logging.getLogger(__name__)
        here = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(here)
        alembic_ini = os.path.join(project_root, "alembic.ini")
        # migrations/ dir is used (not alembic/) to avoid shadowing the alembic PyPI package

        for attempt in range(retries):
            try:
                from alembic.config import Config
                from alembic import command

                cfg = Config(alembic_ini)
                cfg.set_main_option("sqlalchemy.url", self.database_url)

                # Existing deployment with no alembic_version table: stamp head
                # so we skip DDL that already ran via the old _init_db().
                self._auto_stamp_if_needed(cfg)
                command.upgrade(cfg, "head")
                return
            except psycopg2.OperationalError:
                if attempt == retries - 1:
                    raise
                _log.warning("DB connection attempt %d failed, retrying...", attempt + 1)
                time.sleep(delay)

    def _auto_stamp_if_needed(self, cfg) -> None:
        """If the DB has app tables but no alembic_version, stamp head.

        This handles deployments that were initialized by the old inline _init_db()
        before Alembic was introduced, so we skip re-running already-applied DDL.
        """
        from alembic import command
        try:
            conn = psycopg2.connect(
                self.database_url,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('tasks', 'alembic_version')
            """)
            tables = {row["table_name"] for row in cur.fetchall()}
            cur.close()
            conn.close()
            if "tasks" in tables and "alembic_version" not in tables:
                command.stamp(cfg, "head")
        except Exception:
            pass

    # ── Users CRUD ──

    def create_user(self, user_id: str, username: str, password_hash: str,
                    created_at: str = "") -> Dict:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, username, password_hash, created_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING user_id, username, created_at
                """, (user_id, username, password_hash, created_at or self._now()))
                row = cur.fetchone()
            conn.commit()
        return dict(row)

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id, username, password_hash, created_at FROM users WHERE username = %s",
                    (username,))
                row = cur.fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id, username, password_hash, created_at FROM users WHERE user_id = %s",
                    (user_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    # ── 任务 CREATE ──

    def create_task(self, task_id: str, title: str = "", content: str = "",
                    target_audience: str = "管理层", scenario: str = "",
                    language: str = "zh",
                    file_path: str = None, mode: str = "auto",
                    created_at: str = "") -> Dict:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tasks (task_id, title, content, target_audience,
                                       scenario, language, file_path, mode,
                                       created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (task_id, title, content, target_audience, scenario,
                      language, file_path, mode, created_at, created_at))
                for stage in PIPELINE_STAGES:
                    cur.execute("""
                        INSERT INTO pipeline_stages (task_id, stage, status)
                        VALUES (%s, %s, 'pending')
                        ON CONFLICT (task_id, stage) DO NOTHING
                    """, (task_id, stage))
            conn.commit()
        return self.get_task(task_id)

    # ── 任务 READ ──

    def get_task(self, task_id: str) -> Optional[Dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
                row = cur.fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def get_tasks_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM tasks WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                    (status, limit))
                rows = cur.fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_history(self, limit: int = 20) -> List[Dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM tasks "
                    "ORDER BY created_at DESC LIMIT %s", (limit,))
                rows = cur.fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_all_tasks(self, limit: int = 100) -> List[Dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT %s", (limit,))
                rows = cur.fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_by_status(self, status: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM tasks WHERE status = %s", (status,))
                row = cur.fetchone()
        return row["cnt"] if row else 0

    def count_all(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM tasks")
                row = cur.fetchone()
        return row["cnt"] if row else 0

    # ── 任务 UPDATE ──

    def update_task(self, task_id: str, **fields) -> bool:
        allowed = {"status", "progress", "current_step", "current_stage",
                    "message", "output_file", "error", "narrative", "slides",
                    "file_path", "title", "content", "mode"}
        updates = {}
        for k, v in fields.items():
            if k in allowed:
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                updates[k] = v
        if not updates:
            return False
        updates["updated_at"] = self._now()
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [task_id]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE tasks SET {set_clause} WHERE task_id = %s", values)
            conn.commit()
        self._notify(task_id)
        return True

    # ── 任务 DELETE ──

    def delete_task(self, task_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM supplemental_data WHERE task_id = %s", (task_id,))
                cur.execute("DELETE FROM pipeline_stages WHERE task_id = %s", (task_id,))
                cur.execute("DELETE FROM tasks WHERE task_id = %s", (task_id,))
                count = cur.rowcount
            conn.commit()
        return count > 0

    def cleanup_old_tasks(self, days: int = 30) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM supplemental_data WHERE task_id IN "
                    "(SELECT task_id FROM tasks WHERE status = 'completed' "
                    "AND updated_at < NOW() - INTERVAL '1 day' * %s)", (days,))
                cur.execute(
                    "DELETE FROM pipeline_stages WHERE task_id IN "
                    "(SELECT task_id FROM tasks WHERE status = 'completed' "
                    "AND updated_at < NOW() - INTERVAL '1 day' * %s)", (days,))
                cur.execute(
                    "DELETE FROM tasks WHERE status = 'completed' "
                    "AND updated_at < NOW() - INTERVAL '1 day' * %s", (days,))
                count = cur.rowcount
            conn.commit()
        return count

    # ── Pipeline阶段 CRUD ──

    def get_stages(self, task_id: str) -> List[Dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM pipeline_stages WHERE task_id = %s ORDER BY stage",
                    (task_id,))
                rows = cur.fetchall()
        stages_map = {r["stage"]: self._stage_row_to_dict(r) for r in rows}
        result = []
        for stage in PIPELINE_STAGES:
            if stage in stages_map:
                result.append(stages_map[stage])
            else:
                result.append({"stage": stage, "status": "pending",
                               "started_at": None, "completed_at": None,
                               "result": None, "error": None})
        return result

    def get_stage(self, task_id: str, stage: str) -> Optional[Dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM pipeline_stages WHERE task_id = %s AND stage = %s",
                    (task_id, stage))
                row = cur.fetchone()
        if not row:
            return None
        return self._stage_row_to_dict(row)

    def update_stage(self, task_id: str, stage: str, **fields) -> bool:
        allowed = {"status", "result", "error", "started_at", "completed_at"}
        updates = {}
        for k, v in fields.items():
            if k in allowed:
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                updates[k] = v
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [task_id, stage]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE pipeline_stages SET {set_clause} "
                    "WHERE task_id = %s AND stage = %s", values)
            conn.commit()
        return True

    def save_stage_result(self, task_id: str, stage: str, result: Any) -> bool:
        """无条件保存阶段结果，同时递增 generation（乐观锁版本号）。"""
        if isinstance(result, (dict, list)):
            result_json = json.dumps(result, ensure_ascii=False)
        elif isinstance(result, str):
            result_json = result
        else:
            result_json = json.dumps(result, ensure_ascii=False, default=str)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE pipeline_stages
                    SET result = %s, status = 'completed', completed_at = %s,
                        generation = generation + 1
                    WHERE task_id = %s AND stage = %s
                """, (result_json, self._now(), task_id, stage))
            conn.commit()
        return True

    def check_and_save_stage_result(
        self, task_id: str, stage: str, expected_generation: int, result: Any
    ) -> tuple:
        """
        乐观锁保存：仅当 generation == expected_generation 时写入。

        返回 (success: bool, current_generation: int)。
        success=False 表示版本冲突，调用方应返回 HTTP 412。
        """
        if isinstance(result, (dict, list)):
            result_json = json.dumps(result, ensure_ascii=False)
        elif isinstance(result, str):
            result_json = result
        else:
            result_json = json.dumps(result, ensure_ascii=False, default=str)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE pipeline_stages
                    SET result = %s, status = 'completed', completed_at = %s,
                        generation = generation + 1
                    WHERE task_id = %s AND stage = %s AND generation = %s
                """, (result_json, self._now(), task_id, stage, expected_generation))
                rows_affected = cur.rowcount
            conn.commit()

        if rows_affected > 0:
            return True, expected_generation + 1

        # 版本冲突：读取当前 generation 返回给调用方
        current = self.get_stage(task_id, stage)
        current_gen = current.get("generation", 0) if current else 0
        return False, current_gen

    def get_stage_result(self, task_id: str, stage: str) -> Any:
        stage = self.get_stage(task_id, stage)
        if not stage:
            return None
        return stage.get("result")

    def reset_stages_from(self, task_id: str, from_stage: str) -> bool:
        from_idx = PIPELINE_STAGES.index(from_stage) if from_stage in PIPELINE_STAGES else 0
        stages_to_reset = PIPELINE_STAGES[from_idx:]
        with self._connect() as conn:
            with conn.cursor() as cur:
                for stage in stages_to_reset:
                    cur.execute("""
                        UPDATE pipeline_stages
                        SET status = 'pending', result = NULL, error = NULL,
                            started_at = NULL, completed_at = NULL,
                            generation = 0
                        WHERE task_id = %s AND stage = %s
                    """, (task_id, stage))
            conn.commit()
        return True

    def get_latest_completed_stage(self, task_id: str) -> Optional[str]:
        stages = self.get_stages(task_id)
        latest = None
        for s in stages:
            if s["status"] == "completed":
                latest = s["stage"]
        return latest

    # ── Settings CRUD ──

    def save_setting(self, user_id: str, key: str, value: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO settings (user_id, key, value, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, key)
                    DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
                """, (user_id, key, value, self._now()))
            conn.commit()
        return True

    def get_setting(self, user_id: str, key: str) -> Optional[str]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM settings WHERE user_id = %s AND key = %s",
                    (user_id, key))
                row = cur.fetchone()
        return row["value"] if row else None

    def get_all_settings(self, user_id: str) -> Dict[str, str]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key, value FROM settings WHERE user_id = %s", (user_id,))
                rows = cur.fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ── API Keys CRUD ──

    def save_api_key(self, user_id: str, provider: str, encrypted_key: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO api_keys (user_id, provider, encrypted_key, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, provider)
                    DO UPDATE SET encrypted_key = EXCLUDED.encrypted_key, created_at = EXCLUDED.created_at
                """, (user_id, provider, encrypted_key, self._now()))
            conn.commit()
        return True

    def get_api_key(self, user_id: str, provider: str) -> Optional[str]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT encrypted_key FROM api_keys WHERE user_id = %s AND provider = %s",
                    (user_id, provider))
                row = cur.fetchone()
        return row["encrypted_key"] if row else None

    def get_all_api_keys(self, user_id: str) -> List[Dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT provider, encrypted_key, created_at FROM api_keys WHERE user_id = %s",
                    (user_id,))
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def delete_api_key(self, user_id: str, provider: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM api_keys WHERE user_id = %s AND provider = %s",
                    (user_id, provider))
                count = cur.rowcount
            conn.commit()
        return count > 0

    # ── Supplemental Data CRUD ──

    def save_supplemental_data(
        self, task_id: str, data_id: str, stage: str,
        page_number: Optional[int] = None,
        text_data: str = "", file_path: str = "",
    ) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO supplemental_data
                        (task_id, data_id, stage, page_number, text_data, file_path, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (data_id)
                    DO UPDATE SET task_id = EXCLUDED.task_id, stage = EXCLUDED.stage,
                                  page_number = EXCLUDED.page_number, text_data = EXCLUDED.text_data,
                                  file_path = EXCLUDED.file_path, created_at = EXCLUDED.created_at
                """, (task_id, data_id, stage, page_number, text_data, file_path, self._now()))
            conn.commit()
        return True

    def get_supplemental_data(
        self, task_id: str, stage: Optional[str] = None,
        page_number: Optional[int] = None,
    ) -> List[Dict]:
        query = "SELECT * FROM supplemental_data WHERE task_id = %s"
        params: list = [task_id]
        if stage:
            query += " AND stage = %s"
            params.append(stage)
        if page_number is not None:
            query += " AND (page_number = %s OR page_number IS NULL)"
            params.append(page_number)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    def delete_supplemental_data(self, task_id: str, data_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM supplemental_data WHERE task_id = %s AND data_id = %s",
                    (task_id, data_id))
                count = cur.rowcount
            conn.commit()
        return count > 0

    def get_pipeline_model_config(self, user_id: str = "default") -> Dict:
        from models.model_config import PipelineModelConfig
        config_json = self.get_setting(user_id, "pipeline_model_config")
        if config_json:
            try:
                return PipelineModelConfig.model_validate_json(config_json).model_dump()
            except Exception:
                pass
        return PipelineModelConfig().model_dump()

    # ── 内部方法 ──

    def _row_to_dict(self, row) -> Dict:
        d = dict(row)
        for field in ("narrative", "slides"):
            val = d.get(field)
            if val and isinstance(val, str):
                try:
                    d[field] = json.loads(val)
                except json.JSONDecodeError:
                    d[field] = None
        return d

    def _stage_row_to_dict(self, row) -> Dict:
        d = dict(row)
        val = d.get("result")
        if val and isinstance(val, str):
            try:
                d["result"] = json.loads(val)
            except json.JSONDecodeError:
                d["result"] = val
        return d

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.now().isoformat()


# ── 全局单例 ──

_store: Optional[TaskStore] = None


def get_store(database_url: str = None) -> TaskStore:
    global _store
    if _store is None:
        _store = TaskStore(database_url)
    return _store
