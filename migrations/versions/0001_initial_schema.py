"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-04-22
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            target_audience TEXT DEFAULT '管理层',
            scenario TEXT DEFAULT '',
            language TEXT DEFAULT 'zh',
            file_path TEXT,
            status TEXT DEFAULT 'pending',
            mode TEXT DEFAULT 'auto',
            progress INTEGER DEFAULT 0,
            current_step TEXT DEFAULT '初始化',
            current_stage TEXT DEFAULT '',
            message TEXT DEFAULT '',
            created_at TEXT,
            output_file TEXT,
            error TEXT,
            narrative TEXT,
            slides TEXT,
            updated_at TEXT
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_stages (
            task_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            started_at TEXT,
            completed_at TEXT,
            result TEXT,
            error TEXT,
            generation INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (task_id, stage)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT,
            PRIMARY KEY (user_id, key)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            encrypted_key TEXT NOT NULL,
            created_at TEXT,
            PRIMARY KEY (user_id, provider)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS supplemental_data (
            task_id TEXT NOT NULL,
            data_id TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            page_number INTEGER,
            text_data TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            micro_analysis TEXT,
            created_at TEXT
        )
    """)


def downgrade() -> None:
    for table in ("supplemental_data", "users", "api_keys", "settings",
                  "pipeline_stages", "tasks"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
