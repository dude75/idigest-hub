"""Composite index for task list ordering under org/status filters."""

from __future__ import annotations

from alembic import op

revision = "i0j1k2l3m4n5"
down_revision = "h9i0j1k2l3m4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_tasks_org_status_updated", "tasks", ["org_id", "status", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_tasks_org_status_updated", table_name="tasks")
