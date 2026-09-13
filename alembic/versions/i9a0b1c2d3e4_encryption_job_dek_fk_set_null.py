"""encryption_jobs.target_dek_id nullable, ON DELETE SET NULL

Revision ID: i9a0b1c2d3e4
Revises: h8c9d0e1f2a3
Create Date: 2026-09-13 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sqlite_recreate_encryption_jobs() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    op.rename_table("encryption_jobs", "encryption_jobs_old")
    op.create_table(
        "encryption_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("target_dek_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["target_dek_id"],
            ["data_encryption_keys.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO encryption_jobs (
            id, target_dek_id, status, progress_json, error, started_at, completed_at, created_at
        )
        SELECT
            id, target_dek_id, status, progress_json, error, started_at, completed_at, created_at
        FROM encryption_jobs_old
        """
    )
    op.drop_table("encryption_jobs_old")
    op.execute("PRAGMA foreign_keys=ON")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _sqlite_recreate_encryption_jobs()
        return

    op.alter_column("encryption_jobs", "target_dek_id", existing_type=sa.String(length=36), nullable=True)
    op.drop_constraint("encryption_jobs_target_dek_id_fkey", "encryption_jobs", type_="foreignkey")
    op.create_foreign_key(
        "encryption_jobs_target_dek_id_fkey",
        "encryption_jobs",
        "data_encryption_keys",
        ["target_dek_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return

    op.drop_constraint("encryption_jobs_target_dek_id_fkey", "encryption_jobs", type_="foreignkey")
    op.create_foreign_key(
        "encryption_jobs_target_dek_id_fkey",
        "encryption_jobs",
        "data_encryption_keys",
        ["target_dek_id"],
        ["id"],
    )
    op.alter_column("encryption_jobs", "target_dek_id", existing_type=sa.String(length=36), nullable=False)
