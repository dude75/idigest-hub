"""user_tags and user_tag_links for personal library tagging."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("name_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name_key"),
    )
    op.create_table(
        "user_tag_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["user_tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "object_type", "object_id", "tag_id"),
    )
    op.create_index("ix_user_tag_links_user_tag", "user_tag_links", ["user_id", "tag_id"])
    op.create_index("ix_user_tag_links_object", "user_tag_links", ["object_type", "object_id"])


def downgrade() -> None:
    op.drop_index("ix_user_tag_links_object", table_name="user_tag_links")
    op.drop_index("ix_user_tag_links_user_tag", table_name="user_tag_links")
    op.drop_table("user_tag_links")
    op.drop_table("user_tags")
