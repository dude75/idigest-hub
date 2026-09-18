"""worker transcribe model lists and user overrides

Revision ID: q7r8s9t0u1v2
Revises: p6f7a8b9c0d1
Create Date: 2026-09-18 12:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, Sequence[str], None] = "p6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("worker_nodes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("asr_models_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("diarization_models_json", sa.JSON(), nullable=True))
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("asr_model", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("diarization_model", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("diarization_model")
        batch_op.drop_column("asr_model")
    with op.batch_alter_table("worker_nodes", schema=None) as batch_op:
        batch_op.drop_column("diarization_models_json")
        batch_op.drop_column("asr_models_json")
