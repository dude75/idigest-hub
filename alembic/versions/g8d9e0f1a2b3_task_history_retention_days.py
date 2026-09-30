"""instance_settings task_history_retention_days"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g8d9e0f1a2b3"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("task_history_retention_days", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("task_history_retention_days")
