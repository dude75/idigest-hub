"""Money columns Numeric(12,2) -> Numeric(12,3)

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-10-04 12:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, Sequence[str], None] = "j1k2l3m4n5o6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MONEY = sa.Numeric(precision=12, scale=3)
_MONEY_OLD = sa.Numeric(precision=12, scale=2)


def _alter_money(table: str, column: str) -> None:
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.alter_column(
            column,
            existing_type=_MONEY_OLD,
            type_=_MONEY,
            existing_nullable=False,
        )


def upgrade() -> None:
    _alter_money("organizations", "balance")
    _alter_money("tariffs", "signup_credit")
    _alter_money("usage_events", "amount")


def downgrade() -> None:
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.alter_column(
            "balance",
            existing_type=_MONEY,
            type_=_MONEY_OLD,
            existing_nullable=False,
        )
    with op.batch_alter_table("tariffs", schema=None) as batch_op:
        batch_op.alter_column(
            "signup_credit",
            existing_type=_MONEY,
            type_=_MONEY_OLD,
            existing_nullable=False,
        )
    with op.batch_alter_table("usage_events", schema=None) as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=_MONEY,
            type_=_MONEY_OLD,
            existing_nullable=False,
        )
