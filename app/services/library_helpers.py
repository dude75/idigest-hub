"""Shared library router helpers (list badges, filters, upload)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ALLOWED_AUDIO_SUFFIXES, ALLOWED_VIDEO_SUFFIXES, MAX_UPLOAD_BYTES_CAP
from app.deps import AuthContext
from app.errors import ErrorCode
from app.models import Audio, Share, Summary, Transcript, User
from app.presenters import summary_public, transcript_public
from app.services.access import can_read_object, is_hidden, is_shared_with, outgoing_shares
from app.services.export import safe_filename
from app.services.library_list import batch_share_badges, count_hidden_library_rows, list_library_rows
from app.services.upload_validation import InvalidAudioContent
from app.services.user_tags import batch_object_user_tags, object_user_tags
from app.services.storage import PayloadTooLarge, get_storage
from app.services.video_extract import VideoExtractError, cleanup_extract_temp, video_upload_to_mp3_temp
from app.schemas.library import (
    SummaryListItem,
    SummarySourceGroup,
    TranscriptListItem,
    TranscriptSourceGroup,
)

def share_items(db: Session, rows: list[Share]) -> list[dict]:
    if not rows:
        return []
    user_ids = [row.to_user_id for row in rows]
    users = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    }
    return [
        {
            "id": row.id,
            "to_user_id": row.to_user_id,
            "email": users[row.to_user_id].email if row.to_user_id in users else row.to_user_id,
        }
        for row in rows
    ]


def share_badge(
    db: Session,
    object_type: str,
    object_id: str,
    owner_id: str,
    ctx: AuthContext,
    *,
    user_tags: list[dict] | None = None,
) -> dict:
    extra: dict = {}
    if owner_id == ctx.user.id:
        outgoing = outgoing_shares(db, object_type, object_id)
        extra["shared_with"] = [row.to_user_id for row in outgoing]
        extra["shares"] = share_items(db, outgoing)
        extra["share_kind"] = "outgoing" if outgoing else None
    else:
        row = is_shared_with(db, object_type, object_id, ctx.user.id)
        if row:
            from_user = db.get(User, row.from_user_id)
            extra["share_kind"] = "incoming"
            extra["shared_by"] = from_user.email if from_user else row.from_user_id
            extra["share_id"] = row.id
    extra["hidden"] = is_hidden(db, ctx.user.id, object_type, object_id)
    extra["owner_email"] = (db.get(User, owner_id).email if db.get(User, owner_id) else None)
    if user_tags is None:
        user_tags = object_user_tags(db, ctx.user.id, object_type, object_id)
    extra["user_tags"] = user_tags
    return extra


def visible_transcript(ctx: AuthContext, db: Session, transcript: Transcript) -> bool:
    if is_hidden(db, ctx.user.id, "transcript", transcript.id):
        return False
    return can_read_object(
        ctx, db, "transcript", transcript.owner_user_id, transcript.org_id, transcript.id
    ) or ctx.is_org_admin


def visible_summary(ctx: AuthContext, db: Session, summary: Summary) -> bool:
    if is_hidden(db, ctx.user.id, "summary", summary.id):
        return False
    return can_read_object(
        ctx, db, "summary", summary.owner_user_id, summary.org_id, summary.id
    ) or ctx.is_org_admin


def audio_derived_info(db: Session, ctx: AuthContext, audio_ids: list[str]) -> dict[str, dict]:
    if not audio_ids:
        return {}
    transcripts = list(
        db.scalars(
            select(Transcript)
            .where(Transcript.source_audio_id.in_(audio_ids))
            .order_by(Transcript.created_at.desc())
        ).all()
    )
    visible_by_audio: dict[str, list[Transcript]] = {}
    visible_tr_ids: list[str] = []
    for transcript in transcripts:
        audio_id = transcript.source_audio_id
        if not audio_id or not visible_transcript(ctx, db, transcript):
            continue
        visible_by_audio.setdefault(audio_id, []).append(transcript)
        visible_tr_ids.append(transcript.id)

    summary_by_transcript: dict[str, Summary] = {}
    if visible_tr_ids:
        summaries = list(
            db.scalars(
                select(Summary)
                .where(Summary.source_transcript_id.in_(visible_tr_ids))
                .order_by(Summary.created_at.desc())
            ).all()
        )
        for summary in summaries:
            transcript_id = summary.source_transcript_id
            if not transcript_id or not visible_summary(ctx, db, summary):
                continue
            if transcript_id not in summary_by_transcript:
                summary_by_transcript[transcript_id] = summary

    result: dict[str, dict] = {}
    for audio_id in audio_ids:
        visible = visible_by_audio.get(audio_id, [])
        has_transcript = bool(visible)
        transcript_id = visible[0].id if visible else None
        summary_transcript_id = None
        newest_summary_at = None
        for transcript in visible:
            summary = summary_by_transcript.get(transcript.id)
            if summary is None:
                continue
            if newest_summary_at is None or summary.created_at > newest_summary_at:
                newest_summary_at = summary.created_at
                summary_transcript_id = transcript.id
        result[audio_id] = {
            "has_transcript": has_transcript,
            "has_summary": summary_transcript_id is not None,
            "transcript_id": transcript_id,
            "summary_transcript_id": summary_transcript_id,
        }
    return result


def transcript_derived_info(db: Session, ctx: AuthContext, transcript_ids: list[str]) -> dict[str, dict]:
    if not transcript_ids:
        return {}
    has_summary = dict.fromkeys(transcript_ids, False)
    summaries = list(
        db.scalars(
            select(Summary)
            .where(Summary.source_transcript_id.in_(transcript_ids))
            .order_by(Summary.created_at.desc())
        ).all()
    )
    for summary in summaries:
        transcript_id = summary.source_transcript_id
        if not transcript_id or not visible_summary(ctx, db, summary):
            continue
        has_summary[transcript_id] = True
    return {transcript_id: {"has_summary": has_summary[transcript_id]} for transcript_id in transcript_ids}


def count_hidden_for_user(ctx: AuthContext, db: Session, model, object_type: str) -> int:
    return count_hidden_library_rows(ctx, db, model, object_type)


def library_owner_filter(ctx: AuthContext, owner_user_id: str | None) -> str | None:
    if not owner_user_id or not owner_user_id.strip():
        return None
    if not ctx.is_org_admin and not ctx.is_instance_admin:
        ctx.raise_error(ErrorCode.forbidden)
    return owner_user_id.strip()


def list_filter(
    ctx: AuthContext,
    db: Session,
    model,
    object_type: str,
    include_hidden: bool,
    tag: str | None = None,
    owner_user_id: str | None = None,
    q: str | None = None,
    *,
    limit: int | None = None,
    offset: int = 0,
):
    return list_library_rows(
        ctx,
        db,
        model,
        object_type,
        include_hidden,
        tag,
        owner_user_id=owner_user_id,
        q=q,
        limit=limit,
        offset=offset,
    )


def upload_as_video(suffix: str, file: UploadFile) -> bool:
    """Video containers go through ffmpeg extract; audio/webm stays as stored audio."""
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        return False
    if suffix == ".webm":
        ct = (file.content_type or "").split(";", 1)[0].strip().lower()
        if ct.startswith("audio/"):
            return False
    return True


async def store_upload_as_mp3(
    file: UploadFile,
    *,
    suffix: str,
    limit: int,
    storage,
    audio_id: str,
    raw_name: str,
) -> tuple[str, str]:
    mp3_tmp: Path | None = None
    try:
        mp3_tmp = await video_upload_to_mp3_temp(file, suffix=suffix, max_bytes=limit)
        storage_path = await storage.save_file_path(audio_id, ".mp3", mp3_tmp, max_bytes=limit)
    finally:
        if mp3_tmp is not None:
            cleanup_extract_temp(mp3_tmp)
    stem = safe_filename(Path(raw_name).stem or "original")
    return storage_path, f"{stem}.mp3"

def audio_filenames(db: Session, audio_ids: set[str | None]) -> dict[str, str]:
    ids = [audio_id for audio_id in audio_ids if audio_id]
    if not ids:
        return {}
    return {
        audio.id: audio.original_filename
        for audio in db.scalars(select(Audio).where(Audio.id.in_(ids))).all()
    }


def transcripts_by_id(db: Session, transcript_ids: set[str | None]) -> dict[str, Transcript]:
    ids = [transcript_id for transcript_id in transcript_ids if transcript_id]
    if not ids:
        return {}
    return {
        transcript.id: transcript
        for transcript in db.scalars(select(Transcript).where(Transcript.id.in_(ids))).all()
    }


def summary_source_context(
    summary: Summary,
    transcripts: dict[str, Transcript],
    audio_filenames: dict[str, str],
) -> tuple[Transcript | None, str | None]:
    transcript = transcripts.get(summary.source_transcript_id) if summary.source_transcript_id else None
    source_filename = (
        audio_filenames.get(transcript.source_audio_id)
        if transcript and transcript.source_audio_id
        else None
    )
    return transcript, source_filename


def transcript_list_items(
    db: Session,
    ctx: AuthContext,
    rows: list[Transcript],
) -> list[TranscriptListItem]:
    if not rows:
        return []
    tag_map = batch_object_user_tags(db, ctx.user.id, "transcript", [row.id for row in rows])
    badges = batch_share_badges(db, ctx, "transcript", rows, user_tags_by_id=tag_map)
    filenames = audio_filenames(db, {row.source_audio_id for row in rows})
    derived = transcript_derived_info(db, ctx, [row.id for row in rows])
    return [
        TranscriptListItem.model_validate(
            {
                **transcript_public(
                    row,
                    extra=badges.get(row.id),
                    source_filename=filenames.get(row.source_audio_id) if row.source_audio_id else None,
                ),
                **derived.get(row.id, {"has_summary": False}),
                "has_tone_analytics": row.has_tone_analytics,
            }
        )
        for row in rows
    ]


def transcript_source_groups(
    source_ids: list[str | None],
    items: list[TranscriptListItem],
) -> list[TranscriptSourceGroup]:
    by_source: dict[str | None, list[TranscriptListItem]] = {}
    for item in items:
        by_source.setdefault(item.source_audio_id, []).append(item)
    groups: list[TranscriptSourceGroup] = []
    for sid in source_ids:
        group_items = sorted(
            by_source.get(sid, []),
            key=lambda row: row.created_at,
            reverse=True,
        )
        groups.append(TranscriptSourceGroup(source_id=sid, items=group_items))
    return groups


def summary_list_items(
    db: Session,
    ctx: AuthContext,
    rows: list[Summary],
) -> list[SummaryListItem]:
    if not rows:
        return []
    tag_map = batch_object_user_tags(db, ctx.user.id, "summary", [row.id for row in rows])
    badges = batch_share_badges(db, ctx, "summary", rows, user_tags_by_id=tag_map)
    transcripts = transcripts_by_id(db, {row.source_transcript_id for row in rows})
    filenames = audio_filenames(
        db, {tr.source_audio_id for tr in transcripts.values() if tr.source_audio_id}
    )
    items: list[SummaryListItem] = []
    for row in rows:
        source_transcript, source_filename = summary_source_context(row, transcripts, filenames)
        items.append(
            SummaryListItem.model_validate(
                summary_public(
                    row,
                    extra=badges.get(row.id),
                    source_transcript=source_transcript,
                    source_filename=source_filename,
                )
            )
        )
    return items


def summary_source_groups(
    source_ids: list[str | None],
    items: list[SummaryListItem],
) -> list[SummarySourceGroup]:
    by_source: dict[str | None, list[SummaryListItem]] = {}
    for item in items:
        by_source.setdefault(item.source_transcript_id, []).append(item)
    groups: list[SummarySourceGroup] = []
    for sid in source_ids:
        group_items = sorted(
            by_source.get(sid, []),
            key=lambda row: row.created_at,
            reverse=True,
        )
        groups.append(SummarySourceGroup(source_id=sid, items=group_items))
    return groups



def owner_of(db: Session, object_type: str, object_id: str):
    model = {"audio": Audio, "transcript": Transcript, "summary": Summary, "skill": None}[object_type]
    if object_type == "skill":
        from app.models import Skill

        return db.get(Skill, object_id)
    return db.get(model, object_id)


def require_share_owner(
    db: Session, object_type: str, object_id: str, ctx: AuthContext
):
    if object_type not in {"audio", "transcript", "summary", "skill"}:
        ctx.raise_error(ErrorCode.validation_error)
    obj = owner_of(db, object_type, object_id)
    if obj is None:
        ctx.raise_error(ErrorCode.not_found)
    if object_type == "skill":
        if obj.scope != "self" or obj.owner_user_id != ctx.user.id:
            ctx.raise_error(ErrorCode.forbidden)
    elif obj.owner_user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.forbidden)
    return obj


def summary_public_link_access(summary: Summary, ctx: AuthContext, *, owner_only: bool) -> None:
    if ctx.org is None or summary.org_id != ctx.org.id:
        ctx.raise_error(ErrorCode.not_found)
    if owner_only:
        if summary.owner_user_id != ctx.user.id:
            ctx.raise_error(ErrorCode.forbidden)
    elif summary.owner_user_id != ctx.user.id and not ctx.is_org_admin:
        ctx.raise_error(ErrorCode.forbidden)


