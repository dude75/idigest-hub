"""Task visibility and list extras (shared by REST tasks router and MCP)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import AuthContext
from app.models import Audio, Organization, Task, Transcript, User


def can_manage_task(ctx: AuthContext, task: Task) -> bool:
    if ctx.org is None or task.org_id != ctx.org.id:
        return False
    if ctx.is_org_admin:
        return True
    return task.user_id == ctx.user.id


def can_see_task(ctx: AuthContext, task: Task) -> bool:
    if ctx.is_instance_admin:
        return True
    if ctx.org is None or task.org_id != ctx.org.id:
        return False
    if ctx.is_org_admin:
        return True
    return task.user_id == ctx.user.id


def visible_tasks_filters(ctx: AuthContext) -> list:
    if ctx.is_instance_admin:
        return []
    if ctx.org is None:
        return [Task.user_id == ctx.user.id]
    if ctx.is_org_admin:
        if ctx.user.show_only_my_items:
            return [Task.org_id == ctx.org.id, Task.user_id == ctx.user.id]
        return [Task.org_id == ctx.org.id]
    return [Task.org_id == ctx.org.id, Task.user_id == ctx.user.id]


def _import_display_name(meta: dict[str, Any] | None) -> str | None:
    if not meta:
        return None
    title = meta.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    url = meta.get("url")
    if not isinstance(url, str) or not url.strip():
        return None
    parsed = urlparse(url.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if parts:
        return parts[-1]
    if parsed.hostname:
        return parsed.hostname
    return url.strip()


def task_list_extra(db: Session, rows: list[Task]) -> dict[str, dict]:
    user_ids = {row.user_id for row in rows}
    org_ids = {row.org_id for row in rows}
    transcript_ids = {row.transcript_id for row in rows if row.transcript_id}
    users = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
        if user_ids
        else {}
    )
    orgs = (
        {o.id: o for o in db.scalars(select(Organization).where(Organization.id.in_(org_ids))).all()}
        if org_ids
        else {}
    )
    transcripts = (
        {
            transcript.id: transcript
            for transcript in db.scalars(select(Transcript).where(Transcript.id.in_(transcript_ids))).all()
        }
        if transcript_ids
        else {}
    )
    audio_ids = {row.audio_id for row in rows if row.audio_id}
    audio_ids.update(
        transcript.source_audio_id
        for transcript in transcripts.values()
        if transcript.source_audio_id
    )
    audios = (
        {audio.id: audio for audio in db.scalars(select(Audio).where(Audio.id.in_(audio_ids))).all()}
        if audio_ids
        else {}
    )
    extra: dict[str, dict] = {}
    for row in rows:
        user = users.get(row.user_id)
        org = orgs.get(row.org_id)
        audio = audios.get(row.audio_id) if row.audio_id else None
        if audio is None and row.transcript_id:
            transcript = transcripts.get(row.transcript_id)
            if transcript and transcript.source_audio_id:
                audio = audios.get(transcript.source_audio_id)
        audio_filename = audio.original_filename if audio else None
        if audio_filename is None and row.type == "import":
            audio_filename = _import_display_name(row.meta_json)
        if audio_filename is None and row.type == "capture":
            from app.services.capture_meeting import capture_storage_filename

            audio_filename = capture_storage_filename(row.meta_json, ".mp3")
        extra[row.id] = {
            "owner_email": user.email if user else None,
            "org_name": org.name if org else None,
            "audio_filename": audio_filename,
        }
    return extra
