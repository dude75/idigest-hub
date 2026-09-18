"""summary public links and org allow_public_links

Revision ID: p6f7a8b9c0d1
Revises: o5e6f7a8b9c0
Create Date: 2026-09-17 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "o5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("allow_public_links", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("rate_limit_public_link_ip", sa.Integer(), nullable=False, server_default="300")
        )
        batch_op.add_column(
            sa.Column("rate_limit_public_link_global", sa.Integer(), nullable=False, server_default="5000")
        )
        batch_op.add_column(
            sa.Column("rate_limit_public_pin_ip", sa.Integer(), nullable=False, server_default="60")
        )

    op.create_table(
        "summary_public_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("summary_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pin_hash", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["summary_id"], ["summaries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("summary_id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_summary_public_links_org", "summary_public_links", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_summary_public_links_org", table_name="summary_public_links")
    op.drop_table("summary_public_links")
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("rate_limit_public_pin_ip")
        batch_op.drop_column("rate_limit_public_link_global")
        batch_op.drop_column("rate_limit_public_link_ip")
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.drop_column("allow_public_links")
