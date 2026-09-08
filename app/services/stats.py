"""Счётчики завершённых задач и длительности аудио для дашбордов."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Task, UsageEvent


def completed_job_stats(db: Session, *, org_id: str | None = None) -> dict:
    task_filters = []
    if org_id is not None:
        task_filters.append(Task.org_id == org_id)
    transcribe_done = int(
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.type == "transcribe", Task.status == "success", *task_filters)
        )
        or 0
    )
    summarize_done = int(
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.type == "summarize", Task.status == "success", *task_filters)
        )
        or 0
    )
    audio_query = (
        select(func.coalesce(func.sum(UsageEvent.audio_sec), 0))
        .select_from(UsageEvent)
        .join(Task, Task.id == UsageEvent.task_id)
        .where(Task.type == "transcribe", Task.status == "success")
    )
    if org_id is not None:
        audio_query = audio_query.where(Task.org_id == org_id)
    audio_sec = db.scalar(audio_query)
    return {
        "tasks_transcribe_success": transcribe_done,
        "tasks_summarize_success": summarize_done,
        "audio_transcribed_sec": float(audio_sec or 0),
    }
