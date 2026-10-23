"""instance outbound proxy master flag + telegram settings"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m4n5o6p7q8r9"
down_revision = "l3m4n5o6p7q8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instance_settings",
        sa.Column("outbound_proxy_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "instance_settings",
        sa.Column("telegram_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("instance_settings", sa.Column("telegram_bot_token_encrypted", sa.Text(), nullable=True))
    op.add_column(
        "instance_settings",
        sa.Column("telegram_use_proxy", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(sa.text("UPDATE instance_settings SET outbound_proxy_enabled = download_proxy_enabled"))


def downgrade() -> None:
    op.drop_column("instance_settings", "telegram_use_proxy")
    op.drop_column("instance_settings", "telegram_bot_token_encrypted")
    op.drop_column("instance_settings", "telegram_enabled")
    op.drop_column("instance_settings", "outbound_proxy_enabled")
