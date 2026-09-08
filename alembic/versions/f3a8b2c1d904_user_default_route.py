"""users default_route column

Revision ID: f3a8b2c1d904
Revises: e1b4c7d902fa
Create Date: 2026-09-09 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f3a8b2c1d904"
down_revision: Union[str, Sequence[str], None] = "e1b4c7d902fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("default_route", sa.String(length=32), nullable=False, server_default="library")
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("default_route")
