"""landing footer free text on instance settings

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-09-18 19:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v2w3x4y5z6a7"
down_revision: Union[str, Sequence[str], None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("landing_footer_text_en", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("landing_footer_text_ru", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("landing_footer_published", sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("landing_footer_published")
        batch_op.drop_column("landing_footer_text_ru")
        batch_op.drop_column("landing_footer_text_en")
