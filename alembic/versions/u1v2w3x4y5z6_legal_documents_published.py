"""legal document publish flags on instance settings

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-09-18 19:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, Sequence[str], None] = "t0u1v2w3x4y5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("user_agreement_published", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column("personal_data_consent_published", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column("privacy_policy_published", sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("privacy_policy_published")
        batch_op.drop_column("personal_data_consent_published")
        batch_op.drop_column("user_agreement_published")
