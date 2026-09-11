"""Hard-delete / hide артефактов и живые задачи (ТЗ §6–7)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import Audio, HiddenItem, Share, Summary, Task, Transcript
from app.presenters import summary_display_title
from app.services.storage import get_storage


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
    stem = Path(audio.original_filename).stem if audio.original_filename else None
    if stem:
        for transcript in db.scalars(select(Transcript).where(Transcript.source_audio_id == audio.id)):
            if not (transcript.title and transcript.title.strip()):
                transcript.title = stem
    get_storage().delete(audio.storage_path)
    db.delete(audio)
    db.flush()


def hard_delete_transcript(db: Session, transcript: Transcript) -> None:
    cancel_queued_for_source(db, transcript_id=transcript.id)
    wipe_object_shares(db, "transcript", transcript.id)
    _clear_task_produced_refs(db, transcript_id=transcript.id)
    source_filename: str | None = None
    if transcript.source_audio_id:
        audio = db.get(Audio, transcript.source_audio_id)
        if audio:
            source_filename = audio.original_filename
    for summary in db.scalars(select(Summary).where(Summary.source_transcript_id == transcript.id)):
        if not (summary.title and summary.title.strip()):
            summary.title = summary_display_title(
                summary,
                source_transcript=transcript,
                source_filename=source_filename,
            )
    db.delete(transcript)


def hard_delete_summary(db: Session, summary: Summary) -> None:
    wipe_object_shares(db, "summary", summary.id)
    _clear_task_produced_refs(db, summary_id=summary.id)
    db.delete(summary)
