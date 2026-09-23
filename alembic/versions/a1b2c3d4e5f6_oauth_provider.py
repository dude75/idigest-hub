"""OAuth 2.1 provider tables (MCP / Open WebUI)

Revision ID: a1b2c3d4e5f6
Revises: c9d0e1f2a3b4
Create Date: 2026-09-23 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("client_secret_hash", sa.String(length=64), nullable=True),
        sa.Column("client_name", sa.String(length=256), nullable=False),
        sa.Column("redirect_uris_json", sa.JSON(), nullable=False),
        sa.Column("grant_types_json", sa.JSON(), nullable=False),
        sa.Column("response_types_json", sa.JSON(), nullable=False),
        sa.Column("token_endpoint_auth_method", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("redirect_uri", sa.String(length=2048), nullable=False),
        sa.Column("scope", sa.String(length=512), nullable=False),
        sa.Column("resource", sa.String(length=2048), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("code_challenge_method", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index("ix_oauth_authorization_codes_expires_at", "oauth_authorization_codes", ["expires_at"])
    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=512), nullable=False),
        sa.Column("resource", sa.String(length=2048), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )


def downgrade() -> None:
    op.drop_table("oauth_refresh_tokens")
    op.drop_index("ix_oauth_authorization_codes_expires_at", table_name="oauth_authorization_codes")
    op.drop_table("oauth_authorization_codes")
    op.drop_table("oauth_clients")
