"""org_capture_jitsi_hosts: drop worker_id (host JWT only)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("org_capture_jitsi_hosts") as batch:
        batch.drop_column("worker_id")


def downgrade() -> None:
    op.add_column(
        "org_capture_jitsi_hosts",
        sa.Column("worker_id", sa.String(length=36), nullable=True),
    )
