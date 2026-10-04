"""drop summarize job price columns"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tariffs", schema=None) as batch_op:
        batch_op.drop_column("price_per_summarize_job")
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_column("snap_price_per_summarize_job")


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "snap_price_per_summarize_job",
                sa.Numeric(precision=12, scale=2),
                nullable=False,
                server_default="0",
            )
        )
    with op.batch_alter_table("tariffs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "price_per_summarize_job",
                sa.Numeric(precision=12, scale=2),
                nullable=False,
                server_default="0",
            )
        )
