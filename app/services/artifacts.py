"""Hard-delete / hide артефактов и живые задачи (ТЗ §6–7)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import Audio, HiddenItem, Share, Summary, Task, Transcript


def cancel_queued_for_source(db: Session, *, audio_id: str | None = None, transcript_id: str | None = None) -> None:
    q = select(Task).where(Task.status.in_(("queued", "running")))
    if audio_id:
        q = q.where(Task.audio_id == audio_id, Task.type == "transcribe")
    if transcript_id:
        q = q.where(Task.transcript_id == transcript_id, Task.type == "summarize")
    for task in db.scalars(q).all():
        if task.status == "queued" and not task.worker_task_id:
            task.status = "error"
            task.error_code = "canceled"
        elif task.status in {"queued", "running"}:
            task.skip_persist = True
            task.skip_reason = "source_deleted"


def _clear_task_produced_refs(
    db: Session, *, transcript_id: str | None = None, summary_id: str | None = None
) -> None:
    if transcript_id:
        db.execute(
            update(Task)
            .where(Task.produced_transcript_id == transcript_id)
            .values(produced_transcript_id=None)
        )
    if summary_id:
        db.execute(
            update(Task).where(Task.produced_summary_id == summary_id).values(produced_summary_id=None)
        )


def wipe_object_shares(db: Session, object_type: str, object_id: str) -> None:
    db.execute(delete(Share).where(Share.object_type == object_type, Share.object_id == object_id))
    db.execute(
        delete(HiddenItem).where(HiddenItem.object_type == object_type, HiddenItem.object_id == object_id)
    )


def hard_delete_audio(db: Session, audio: Audio) -> None:
    cancel_queued_for_source(db, audio_id=audio.id)
    wipe_object_shares(db, "audio", audio.id)
    path = Path(audio.storage_path)
    if path.is_file():
        path.unlink(missing_ok=True)
    parent = path.parent
    db.delete(audio)
    db.flush()
    if parent.is_dir():
        try:
            next(parent.iterdir())
        except StopIteration:
            parent.rmdir()
        except OSError:
            pass


def hard_delete_transcript(db: Session, transcript: Transcript) -> None:
    cancel_queued_for_source(db, transcript_id=transcript.id)
    wipe_object_shares(db, "transcript", transcript.id)
    _clear_task_produced_refs(db, transcript_id=transcript.id)
    db.delete(transcript)


def hard_delete_summary(db: Session, summary: Summary) -> None:
    wipe_object_shares(db, "summary", summary.id)
    _clear_task_produced_refs(db, summary_id=summary.id)
    db.delete(summary)
