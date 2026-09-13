"""envelope encryption: DEK tables and active_dek_id

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-09-13 00:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_encryption_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("wrapped_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "encryption_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("target_dek_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["target_dek_id"], ["data_encryption_keys.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("active_dek_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_instance_settings_active_dek_id",
            "data_encryption_keys",
            ["active_dek_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_constraint("fk_instance_settings_active_dek_id", type_="foreignkey")
        batch_op.drop_column("active_dek_id")
    op.drop_table("encryption_jobs")
    op.drop_table("data_encryption_keys")
