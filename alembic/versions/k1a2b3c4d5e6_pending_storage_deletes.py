"""pending_storage_deletes queue for durable blob cleanup

Revision ID: k1a2b3c4d5e6
Revises: j0b1c2d3e4f5
Create Date: 2026-09-14 23:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "j0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_storage_deletes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_path"),
    )
    op.create_index(
        "ix_pending_storage_deletes_created_at",
        "pending_storage_deletes",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pending_storage_deletes_created_at", table_name="pending_storage_deletes")
    op.drop_table("pending_storage_deletes")
