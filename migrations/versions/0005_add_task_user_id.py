"""Add user_id column to tasks table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-27
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id VARCHAR(36)")


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS user_id")
