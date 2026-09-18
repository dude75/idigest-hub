"""instance_settings URL import columns

Revision ID: c9f1a2b3d4e5
Revises: b1d4e8f2a903, f8a2c3d4e901
Create Date: 2026-09-11 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9f1a2b3d4e5"
down_revision: Union[str, Sequence[str], None] = ("b1d4e8f2a903", "f8a2c3d4e901")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("import_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("import_allowed_extractors_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("download_proxy_url", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("download_proxy_password_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.drop_column("download_proxy_password_encrypted")
        batch_op.drop_column("download_proxy_url")
        batch_op.drop_column("import_allowed_extractors_json")
        batch_op.drop_column("import_enabled")
