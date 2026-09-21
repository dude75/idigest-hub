"""organizations.capture_bot_display_name"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("capture_bot_display_name", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "capture_bot_display_name")
