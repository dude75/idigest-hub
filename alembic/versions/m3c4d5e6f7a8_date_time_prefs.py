"""instance and user date/time display preferences

Revision ID: m3c4d5e6f7a8
Revises: l2b3c4d5e6f7
Create Date: 2026-09-16 16:05:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "l2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("date_time_format", sa.String(length=16), nullable=False, server_default="eu_24h")
        )
        batch_op.add_column(
            sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC")
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("date_time_format", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("timezone", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("timezone")
        batch_op.drop_column("date_time_format")

    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("timezone")
        batch_op.drop_column("date_time_format")
