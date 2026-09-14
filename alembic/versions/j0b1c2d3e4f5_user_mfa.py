"""User TOTP 2FA, org mfa_required, challenges, recovery codes

Revision ID: j0b1c2d3e4f5
Revises: i9a0b1c2d3e4
Create Date: 2026-09-14 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "i9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "mfa_challenges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_mfa_challenges_user_id", "mfa_challenges", ["user_id"])
    op.create_index("ix_mfa_challenges_expires_at", "mfa_challenges", ["expires_at"])
    op.create_table(
        "recovery_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index("ix_recovery_codes_user_id", "recovery_codes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_recovery_codes_user_id", table_name="recovery_codes")
    op.drop_table("recovery_codes")
    op.drop_index("ix_mfa_challenges_expires_at", table_name="mfa_challenges")
    op.drop_index("ix_mfa_challenges_user_id", table_name="mfa_challenges")
    op.drop_table("mfa_challenges")
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("mfa_required")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("totp_enabled_at")
        batch_op.drop_column("totp_secret_encrypted")
