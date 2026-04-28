"""Make tasks.user_id NOT NULL

Prerequisite: all tasks rows must have a non-null user_id.
Run backfill_task_user_id.py before this migration.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-27
"""
from alembic import op
from sqlalchemy import text

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safety check: fail fast if any rows still have NULL user_id
    conn = op.get_bind()
    result = conn.execute(text("SELECT COUNT(*) FROM tasks WHERE user_id IS NULL"))
    null_count = result.scalar()
    if null_count and null_count > 0:
        raise RuntimeError(
            f"Cannot set NOT NULL: {null_count} tasks still have user_id IS NULL. "
            "Run scripts/backfill_task_user_id.py first."
        )
    op.execute("ALTER TABLE tasks ALTER COLUMN user_id SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE tasks ALTER COLUMN user_id DROP NOT NULL")
