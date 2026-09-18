"""personal data consent and privacy policy legal documents

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-09-18 19:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t0u1v2w3x4y5"
down_revision: Union[str, Sequence[str], None] = "s9t0u1v2w3x4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("personal_data_consent_text_en", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("personal_data_consent_text_ru", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("personal_data_consent_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("privacy_policy_text_en", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("privacy_policy_text_ru", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("privacy_policy_version", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("personal_data_consent_accepted_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("privacy_policy_accepted_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("privacy_policy_accepted_version")
        batch_op.drop_column("personal_data_consent_accepted_version")

    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("privacy_policy_version")
        batch_op.drop_column("privacy_policy_text_ru")
        batch_op.drop_column("privacy_policy_text_en")
        batch_op.drop_column("personal_data_consent_version")
        batch_op.drop_column("personal_data_consent_text_ru")
        batch_op.drop_column("personal_data_consent_text_en")
