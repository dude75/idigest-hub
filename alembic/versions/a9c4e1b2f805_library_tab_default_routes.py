"""split library default_route into tab-specific routes

Revision ID: a9c4e1b2f805
Revises: f3a8b2c1d904
Create Date: 2026-09-09 02:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a9c4e1b2f805"
down_revision: Union[str, Sequence[str], None] = "f3a8b2c1d904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET default_route = 'library/audio' WHERE default_route = 'library'")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "default_route",
            existing_type=sa.String(length=32),
            server_default="library/audio",
        )


def downgrade() -> None:
    op.execute("UPDATE users SET default_route = 'library' WHERE default_route LIKE 'library/%'")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "default_route",
            existing_type=sa.String(length=32),
            server_default="library",
        )
