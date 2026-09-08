"""instance_settings rate limit columns

Revision ID: e1b4c7d902fa
Revises: d7f2a1c8e903
Create Date: 2026-09-09 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e1b4c7d902fa"
down_revision: Union[str, Sequence[str], None] = "d7f2a1c8e903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("rate_limit_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("rate_limit_login_email", sa.Integer(), nullable=False, server_default="30"))
        batch_op.add_column(sa.Column("rate_limit_login_ip", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("rate_limit_login_global", sa.Integer(), nullable=False, server_default="500"))
        batch_op.add_column(sa.Column("rate_limit_signup_email", sa.Integer(), nullable=False, server_default="10"))
        batch_op.add_column(sa.Column("rate_limit_signup_ip", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("rate_limit_signup_global", sa.Integer(), nullable=False, server_default="100"))
        batch_op.add_column(sa.Column("rate_limit_reset_email", sa.Integer(), nullable=False, server_default="10"))
        batch_op.add_column(sa.Column("rate_limit_reset_ip", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("rate_limit_reset_global", sa.Integer(), nullable=False, server_default="50"))
        batch_op.add_column(sa.Column("rate_limit_reset_confirm_ip", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(
            sa.Column("rate_limit_reset_confirm_global", sa.Integer(), nullable=False, server_default="100")
        )
        batch_op.add_column(sa.Column("rate_limit_setup_ip", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("rate_limit_setup_global", sa.Integer(), nullable=False, server_default="10"))
        batch_op.add_column(sa.Column("rate_limit_api_user", sa.Integer(), nullable=False, server_default="120"))
        batch_op.add_column(sa.Column("rate_limit_api_ip", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("rate_limit_api_global", sa.Integer(), nullable=False, server_default="2000"))
        batch_op.add_column(sa.Column("rate_limit_api_tasks_user", sa.Integer(), nullable=False, server_default="30"))
        batch_op.add_column(sa.Column("rate_limit_api_tasks_ip", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        for column in (
            "rate_limit_api_tasks_ip",
            "rate_limit_api_tasks_user",
            "rate_limit_api_global",
            "rate_limit_api_ip",
            "rate_limit_api_user",
            "rate_limit_setup_global",
            "rate_limit_setup_ip",
            "rate_limit_reset_confirm_global",
            "rate_limit_reset_confirm_ip",
            "rate_limit_reset_global",
            "rate_limit_reset_ip",
            "rate_limit_reset_email",
            "rate_limit_signup_global",
            "rate_limit_signup_ip",
            "rate_limit_signup_email",
            "rate_limit_login_global",
            "rate_limit_login_ip",
            "rate_limit_login_email",
            "rate_limit_enabled",
        ):
            batch_op.drop_column(column)
