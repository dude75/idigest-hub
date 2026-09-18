"""tariff metering pack

Revision ID: a8c31f0b9d22
Revises: c4e81f9a2b10
Create Date: 2026-09-08 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a8c31f0b9d22"
down_revision: Union[str, Sequence[str], None] = "c4e81f9a2b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tariffs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("price_per_1k_summary_chars", sa.Numeric(precision=12, scale=6), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("audio_retention_days", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("api_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("signup_credit", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"))
    op.execute("UPDATE tariffs SET price_per_1k_summary_chars = price_per_generated_text")
    with op.batch_alter_table("tariffs", schema=None) as batch_op:
        batch_op.drop_column("price_per_generated_text")

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "snap_price_per_1k_summary_chars",
                sa.Numeric(precision=12, scale=6),
                nullable=False,
                server_default="0",
            )
        )
    op.execute("UPDATE tasks SET snap_price_per_1k_summary_chars = snap_price_per_generated_text")
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_column("snap_price_per_generated_text")

    with op.batch_alter_table("usage_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("summary_chars", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("usage_events", schema=None) as batch_op:
        batch_op.drop_column("summary_chars")
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("snap_price_per_generated_text", sa.Numeric(precision=12, scale=6), nullable=False, server_default="0")
        )
    op.execute("UPDATE tasks SET snap_price_per_generated_text = snap_price_per_1k_summary_chars")
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_column("snap_price_per_1k_summary_chars")
    with op.batch_alter_table("tariffs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("price_per_generated_text", sa.Numeric(precision=12, scale=6), nullable=False, server_default="0")
        )
    op.execute("UPDATE tariffs SET price_per_generated_text = price_per_1k_summary_chars")
    with op.batch_alter_table("tariffs", schema=None) as batch_op:
        batch_op.drop_column("price_per_1k_summary_chars")
        batch_op.drop_column("audio_retention_days")
        batch_op.drop_column("api_enabled")
        batch_op.drop_column("signup_credit")
