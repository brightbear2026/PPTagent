"""Add generation column to pipeline_stages for optimistic locking

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-22
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN IF NOT EXISTS is safe on PostgreSQL 9.6+
    op.execute("""
        ALTER TABLE pipeline_stages
        ADD COLUMN IF NOT EXISTS generation INTEGER NOT NULL DEFAULT 0
    """)
    # Back-fill tasks columns added in early migrations
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'auto'")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS current_stage TEXT DEFAULT ''")
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS scenario TEXT DEFAULT ''")


def downgrade() -> None:
    op.execute("ALTER TABLE pipeline_stages DROP COLUMN IF EXISTS generation")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS mode")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS current_stage")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS scenario")
