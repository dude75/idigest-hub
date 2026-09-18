"""legal document and landing footer Spanish text columns

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-09-18 20:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w3x4y5z6a7b8"
down_revision: Union[str, Sequence[str], None] = "v2w3x4y5z6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_agreement_text_es", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("personal_data_consent_text_es", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("privacy_policy_text_es", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("landing_footer_text_es", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("landing_footer_text_es")
        batch_op.drop_column("privacy_policy_text_es")
        batch_op.drop_column("personal_data_consent_text_es")
        batch_op.drop_column("user_agreement_text_es")
