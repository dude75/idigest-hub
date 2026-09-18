"""user agreement on instance settings and users

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-09-18 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, Sequence[str], None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_agreement_text_en", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("user_agreement_text_ru", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("user_agreement_version", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_agreement_accepted_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("user_agreement_accepted_version")

    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("user_agreement_version")
        batch_op.drop_column("user_agreement_text_ru")
        batch_op.drop_column("user_agreement_text_en")
