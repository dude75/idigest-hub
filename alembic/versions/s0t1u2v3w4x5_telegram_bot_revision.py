"""instance_settings telegram_bot_revision"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s0t1u2v3w4x5"
down_revision = "r9s0t1u2v3w4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instance_settings",
        sa.Column("telegram_bot_revision", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("instance_settings", "telegram_bot_revision")
