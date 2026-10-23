"""Task terminal hooks: metrics + Telegram notifications."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Task
from app.prometheus_metrics import observe_task_terminal


def mark_task_terminal(db: Session, task: Task) -> None:
    if task.status not in {"success", "error"}:
        return
    observe_task_terminal(task)
    from app.services.telegram_bot import notify_task_terminal

    notify_task_terminal(db, task)
