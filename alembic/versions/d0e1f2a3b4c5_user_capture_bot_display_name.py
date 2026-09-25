"""users.capture_bot_display_name"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("capture_bot_display_name", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "capture_bot_display_name")
