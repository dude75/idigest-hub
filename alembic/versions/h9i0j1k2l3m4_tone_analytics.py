"""tone analytics tariff, user pref, transcript flag, task snap"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h9i0j1k2l3m4"
down_revision = "g8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tariffs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("tone_analytics_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("tone_analytics_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    with op.batch_alter_table("transcripts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("has_tone_analytics", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("snap_tone_analytics", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_column("snap_tone_analytics")
    with op.batch_alter_table("transcripts", schema=None) as batch_op:
        batch_op.drop_column("has_tone_analytics")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("tone_analytics_enabled")
    with op.batch_alter_table("tariffs", schema=None) as batch_op:
        batch_op.drop_column("tone_analytics_enabled")
