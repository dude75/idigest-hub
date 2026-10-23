"""telegram account links and link challenges"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instance_settings", sa.Column("telegram_webhook_secret", sa.String(length=64), nullable=True))
    op.create_table(
        "telegram_links",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("telegram_user_id", sa.String(length=32), nullable=False),
        sa.Column("chat_id", sa.String(length=32), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("telegram_user_id", name="uq_telegram_links_telegram_user_id"),
    )
    op.create_table(
        "telegram_link_challenges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_telegram_link_challenges_user_id"),
    )


def downgrade() -> None:
    op.drop_table("telegram_link_challenges")
    op.drop_table("telegram_links")
    op.drop_column("instance_settings", "telegram_webhook_secret")
