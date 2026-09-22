"""instance/user summarize_model + task snap_summarize_model"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instance_settings", sa.Column("summarize_model", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("summarize_model", sa.String(255), nullable=True))
    op.add_column("tasks", sa.Column("snap_summarize_model", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "snap_summarize_model")
    op.drop_column("users", "summarize_model")
    op.drop_column("instance_settings", "summarize_model")
