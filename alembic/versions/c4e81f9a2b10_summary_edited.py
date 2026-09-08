"""summary edited flag

Revision ID: c4e81f9a2b10
Revises: 2eb2064cc4b4
Create Date: 2026-09-08 11:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4e81f9a2b10'
down_revision: Union[str, Sequence[str], None] = '2eb2064cc4b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('summaries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('edited', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('summaries', schema=None) as batch_op:
        batch_op.drop_column('edited')
