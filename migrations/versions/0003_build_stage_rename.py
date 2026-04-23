"""Migrate old 'build' pipeline stage to 'design' + 'render'

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-22
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # For each task that has a completed 'build' stage but no 'design'/'render',
    # synthesize the two successor rows so the pipeline state is consistent.
    op.execute("""
        INSERT INTO pipeline_stages (task_id, stage, status, started_at, completed_at)
        SELECT b.task_id, 'design', b.status, b.started_at, b.completed_at
        FROM pipeline_stages b
        WHERE b.stage = 'build'
          AND b.status IN ('completed', 'running')
          AND NOT EXISTS (
              SELECT 1 FROM pipeline_stages d
              WHERE d.task_id = b.task_id AND d.stage = 'design'
          )
        ON CONFLICT (task_id, stage) DO NOTHING
    """)
    op.execute("""
        INSERT INTO pipeline_stages (task_id, stage, status, started_at, completed_at)
        SELECT b.task_id, 'render', b.status, b.started_at, b.completed_at
        FROM pipeline_stages b
        WHERE b.stage = 'build'
          AND b.status IN ('completed', 'running')
          AND NOT EXISTS (
              SELECT 1 FROM pipeline_stages r
              WHERE r.task_id = b.task_id AND r.stage = 'render'
          )
        ON CONFLICT (task_id, stage) DO NOTHING
    """)
    op.execute("""
        UPDATE tasks
        SET current_stage = 'render'
        WHERE current_stage = 'build'
    """)


def downgrade() -> None:
    # Non-destructive: just remove the synthesized rows
    op.execute("""
        DELETE FROM pipeline_stages
        WHERE stage IN ('design', 'render')
          AND task_id IN (
              SELECT task_id FROM pipeline_stages WHERE stage = 'build'
          )
    """)
