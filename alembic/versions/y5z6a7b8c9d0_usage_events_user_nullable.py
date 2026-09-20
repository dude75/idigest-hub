"""usage_events.user_id nullable for org billing after account delete

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-09-21 12:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y5z6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "x4y5z6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("usage_events", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("usage_events", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.String(length=36), nullable=False)
