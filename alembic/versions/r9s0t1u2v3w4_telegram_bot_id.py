"""telegram bot id and per-link bot instance"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r9s0t1u2v3w4"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instance_settings", sa.Column("telegram_bot_id", sa.BigInteger(), nullable=True))
    op.add_column("telegram_links", sa.Column("instance_bot_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("telegram_links", "instance_bot_id")
    op.drop_column("instance_settings", "telegram_bot_id")
