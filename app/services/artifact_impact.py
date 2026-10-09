"""Preview who is affected by permanent library artifact deletion."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Audio, Share, Summary, Task, Transcript, User
from app.presenters import summary_display_title, transcript_display_title


def _share_recipients(db: Session, object_type: str, object_id: str) -> list[dict[str, str]]:
    rows = db.execute(
        select(User.email)
        .select_from(Share)
        .join(User, User.id == Share.to_user_id)
        .where(Share.object_type == object_type, Share.object_id == object_id)
        .order_by(User.email)
    ).all()
    return [{"email": email} for (email,) in rows]


def _active_task_counts(db: Session, *, audio_id: str | None = None, transcript_id: str | None = None) -> dict[str, int]:
    q = select(Task.status, func.count()).where(Task.status.in_(("queued", "running"))).group_by(Task.status)
    if audio_id:
        q = q.where(Task.audio_id == audio_id, Task.type == "transcribe")
    elif transcript_id:
        q = q.where(Task.transcript_id == transcript_id, Task.type == "summarize")
    else:
        return {"queued": 0, "running": 0}
    counts = {"queued": 0, "running": 0}
    for status, n in db.execute(q).all():
        counts[str(status)] = int(n)
    return counts


def compute_audio_delete_impact(db: Session, audio: Audio) -> dict:
    transcripts = list(db.scalars(select(Transcript).where(Transcript.source_audio_id == audio.id)).all())
    transcript_items = [
        {
            "id": row.id,
            "title": transcript_display_title(row, source_filename=audio.original_filename),
        }
        for row in transcripts
    ]
    return {
        "shared_with": _share_recipients(db, "audio", audio.id),
        "transcripts": transcript_items,
        "summaries": [],
        "active_tasks": _active_task_counts(db, audio_id=audio.id),
    }


def compute_transcript_delete_impact(db: Session, transcript: Transcript) -> dict:
    source_audio = db.get(Audio, transcript.source_audio_id) if transcript.source_audio_id else None
    source_filename = source_audio.original_filename if source_audio else None
    summaries = list(
        db.scalars(select(Summary).where(Summary.source_transcript_id == transcript.id).order_by(Summary.created_at))
        .all()
    )
    summary_items = [
        {
            "id": row.id,
            "title": summary_display_title(
                row,
                source_transcript=transcript,
                source_filename=source_filename,
            ),
        }
        for row in summaries
    ]
    return {
        "shared_with": _share_recipients(db, "transcript", transcript.id),
        "transcripts": [],
        "summaries": summary_items,
        "active_tasks": _active_task_counts(db, transcript_id=transcript.id),
    }
