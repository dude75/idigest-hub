"""task produced artifact FK on delete set null

Revision ID: d7f2a1c8e903
Revises: a8c31f0b9d22
Create Date: 2026-09-08 22:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

revision: str = "d7f2a1c8e903"
down_revision: Union[str, Sequence[str], None] = "a8c31f0b9d22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sqlite_recreate_tasks_table() -> None:
    bind = op.get_bind()
    columns = [col["name"] for col in inspect(bind).get_columns("tasks")]
    quoted = ", ".join(columns)
    bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    bind.exec_driver_sql("ALTER TABLE tasks RENAME TO tasks_old")
    for index in ("ix_tasks_org_status", "ix_tasks_status"):
        bind.exec_driver_sql(f"DROP INDEX IF EXISTS {index}")
    from app.models import Task

    Task.__table__.create(bind)
    bind.exec_driver_sql(f"INSERT INTO tasks ({quoted}) SELECT {quoted} FROM tasks_old")
    bind.exec_driver_sql("DROP TABLE tasks_old")
    bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _sqlite_recreate_tasks_table()
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
