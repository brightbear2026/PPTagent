"""Drop dead micro_analysis column from supplemental_data

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-22
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE supplemental_data DROP COLUMN IF EXISTS micro_analysis")


def downgrade() -> None:
    op.execute("ALTER TABLE supplemental_data ADD COLUMN IF NOT EXISTS micro_analysis TEXT")
