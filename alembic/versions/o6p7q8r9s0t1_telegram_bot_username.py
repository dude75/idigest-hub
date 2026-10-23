"""instance_settings telegram_bot_username"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instance_settings", sa.Column("telegram_bot_username", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("instance_settings", "telegram_bot_username")
