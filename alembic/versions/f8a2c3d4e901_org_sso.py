"""organization SSO columns

Revision ID: f8a2c3d4e901
Revises: e1b4c7d902fa
Create Date: 2026-09-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f8a2c3d4e901"
down_revision: Union[str, Sequence[str], None] = "e1b4c7d902fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sso_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("sso_issuer", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("sso_client_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("sso_client_secret_encrypted", sa.Text(), nullable=True))
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sso_sub", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("sso_sub")
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.drop_column("sso_client_secret_encrypted")
        batch_op.drop_column("sso_client_id")
        batch_op.drop_column("sso_issuer")
        batch_op.drop_column("sso_enabled")
