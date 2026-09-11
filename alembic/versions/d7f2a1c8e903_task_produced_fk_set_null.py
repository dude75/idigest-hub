"""task produced artifact FK on delete set null

Revision ID: d7f2a1c8e903
Revises: a8c31f0b9d22
Create Date: 2026-09-08 22:05:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d7f2a1c8e903"
down_revision: Union[str, Sequence[str], None] = "a8c31f0b9d22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        from app.db import _apply_task_produced_fk_patch

        _apply_task_produced_fk_patch(bind, engine=bind.engine)
        return

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("tasks_produced_transcript_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "tasks_produced_transcript_id_fkey",
            "transcripts",
            ["produced_transcript_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.drop_constraint("tasks_produced_summary_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "tasks_produced_summary_id_fkey",
            "summaries",
            ["produced_summary_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite downgrade is a no-op; FK behavior is enforced in application code.
        return

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("tasks_produced_summary_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "tasks_produced_summary_id_fkey",
            "summaries",
            ["produced_summary_id"],
            ["id"],
        )
        batch_op.drop_constraint("tasks_produced_transcript_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "tasks_produced_transcript_id_fkey",
            "transcripts",
            ["produced_transcript_id"],
            ["id"],
        )
