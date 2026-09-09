"""transcript and summary title

Revision ID: b1d4e8f2a903
Revises: a9c4e1b2f805
Create Date: 2026-09-09 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b1d4e8f2a903"
down_revision: Union[str, Sequence[str], None] = "a9c4e1b2f805"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transcripts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
    with op.batch_alter_table("summaries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("summaries", schema=None) as batch_op:
        batch_op.drop_column("title")
    with op.batch_alter_table("transcripts", schema=None) as batch_op:
        batch_op.drop_column("title")
