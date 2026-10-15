"""users first_name, last_name, profile_name_override"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l3m4n5o6p7q8"
down_revision = "k2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=128), nullable=True))
    op.add_column(
        "users",
        sa.Column("profile_name_override", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "profile_name_override")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
