"""MCP poll and OAuth endpoint rate limits

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-24 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("rate_limit_mcp_poll_user", sa.Integer(), nullable=False, server_default="90")
        )
        batch_op.add_column(
            sa.Column("rate_limit_oauth_register_ip", sa.Integer(), nullable=False, server_default="10")
        )
        batch_op.add_column(
            sa.Column("rate_limit_oauth_register_global", sa.Integer(), nullable=False, server_default="50")
        )
        batch_op.add_column(
            sa.Column("rate_limit_oauth_token_ip", sa.Integer(), nullable=False, server_default="120")
        )
        batch_op.add_column(
            sa.Column("rate_limit_oauth_token_global", sa.Integer(), nullable=False, server_default="500")
        )


def downgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("rate_limit_oauth_token_global")
        batch_op.drop_column("rate_limit_oauth_token_ip")
        batch_op.drop_column("rate_limit_oauth_register_global")
        batch_op.drop_column("rate_limit_oauth_register_ip")
        batch_op.drop_column("rate_limit_mcp_poll_user")
