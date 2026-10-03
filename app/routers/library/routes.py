"""Аудио, транскрипты, саммари, hide/wipe, шары (ТЗ §7–8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import Depends, Form, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import (
    ALLOWED_AUDIO_SUFFIXES,
    ALLOWED_VIDEO_SUFFIXES,
    MAX_UPLOAD_BYTES_CAP,
)
from app.crypto import decrypt_str, encrypt_str
from app.db import get_session
from app.deps import AuthContext, require_auth, require_oauth_scope
from app.services.oauth_scopes import SCOPE_TRANSCRIPTS_READ
from app.errors import ApiError, ErrorCode
from app.models import Audio, HiddenItem, Share, Summary, SummaryPublicLink, Transcript, User, new_id
from app.presenters import (
    audio_public,
    summary_display_title,
    summary_public,
    transcript_display_title,
    transcript_public,
)
from app.services.access import (
    can_read_object,
    ensure_object_share,
    is_hidden,
    is_shared_with,
    outgoing_shares,
    revoke_paired_audio_share,
)
from app.services.artifacts import hard_delete_audio, hard_delete_summary, hard_delete_transcript
from app.services.dispatcher import utterances_to_text
from app.services.transcript_payload import (
    decode_transcript_payload,
    export_json_payload,
    extract_utterances,
    payload_tone_fields,
)
from app.services.export import attachment_response, safe_filename, unwrap_markdown_fence
from app.rate_limit import enforce_write_limits, get_rate_limits
from app.services.audit import write_audit
from app.services.storage import PayloadTooLarge, get_storage
from app.services.upload_validation import InvalidAudioContent
from app.services.library_list import (
    LIBRARY_LIST_MAX_LIMIT,
    LIBRARY_SEARCH_MAX_LEN,
    batch_share_badges,
    count_hidden_library_rows,
    count_library_rows,
    count_library_source_groups,
    list_library_rows,
    list_library_source_group_page,
)
from app.services.user_tags import batch_object_user_tags, object_user_tags, resolve_user_tag
from app.services.video_extract import VideoExtractError, cleanup_extract_temp, video_upload_to_mp3_temp
from app.schemas.library import (
    ShareBody,
    TitlePatch,
    SummaryPatch,
    SummaryPublicLinkBody,
    AudioDetailResponse,
    AudioListItem,
    AudioListResponse,
    SummaryDetailResponse,
    SummaryListItem,
    SummaryListResponse,
    SummarySourceGroup,
    TranscriptDetailResponse,
    TranscriptListItem,
    TranscriptListResponse,
    TranscriptSourceGroup,
    _derived_audio_defaults,
)
from app.services.billing import upload_limit
from app.timeutil import utcnow
from app.services import library_helpers as lh

from app.routers.library._router import router


@router.get("/capture/platforms")
def capture_platforms(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org()
    from app.deps import get_instance_settings
    from app.services.capture_meeting import normalize_host, org_jitsi_hosts_public
    from app.services.capture_platforms import allowed_connectors, public_connectors

    settings = get_instance_settings(db)
    allowed = allowed_connectors(settings)
    jitsi_hosts: list[str] = []
    if settings.capture_enabled and "jitsi" in allowed:
        seen: set[str] = set()
        for item in org_jitsi_hosts_public(db, org.id):
            host = normalize_host(str(item.get("host") or ""))
            if host and host not in seen:
                seen.add(host)
                jitsi_hosts.append(host)
    return {
        "enabled": settings.capture_enabled,
        "connectors": public_connectors(settings, db),
        "jitsi_hosts": jitsi_hosts,
    }


@router.get("/import/platforms")
def import_platforms(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    ctx.require_org()
    from app.deps import get_instance_settings
    from app.services.import_platforms import public_platforms

    from app.services.download_proxy_health import download_proxy_status

    settings = get_instance_settings(db)
    return {
        "enabled": settings.import_enabled,
        "platforms": public_platforms(settings),
        **download_proxy_status(settings, db),
    }


@router.post("/audios")
async def upload_audio(
    request: Request,
    file: UploadFile,
    from_microphone: bool = Form(False),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org()
    enforce_write_limits(request, ctx.user.id, get_rate_limits(db), ctx.locale)
    suffix = Path(file.filename or "").suffix.lower()
    is_video = lh.upload_as_video(suffix, file)
    if suffix not in ALLOWED_AUDIO_SUFFIXES and not is_video:
        ctx.raise_error(ErrorCode.invalid_file)
    limit = min(upload_limit(org.tariff), MAX_UPLOAD_BYTES_CAP)
    raw_cl = request.headers.get("content-length")
    if raw_cl is not None:
        try:
            if int(raw_cl) > limit + 4096:
                ctx.raise_error(ErrorCode.payload_too_large)
        except ValueError:
            pass
    audio_id = new_id()
    storage = get_storage()
    raw_name = file.filename or f"original{suffix}"
    if is_video or from_microphone:
        try:
            storage_path, original_filename = await lh.store_upload_as_mp3(
                file,
                suffix=suffix,
                limit=limit,
                storage=storage,
                audio_id=audio_id,
                raw_name=raw_name,
            )
        except PayloadTooLarge:
            ctx.raise_error(ErrorCode.payload_too_large)
        except VideoExtractError:
            ctx.raise_error(ErrorCode.invalid_file)
        except InvalidAudioContent:
            ctx.raise_error(ErrorCode.invalid_file)
    else:
        try:
            storage_path = await storage.save_upload(audio_id, suffix, file, max_bytes=limit)
        except PayloadTooLarge:
            ctx.raise_error(ErrorCode.payload_too_large)
        except InvalidAudioContent:
            ctx.raise_error(ErrorCode.invalid_file)
        original_filename = raw_name
    row = Audio(
        id=audio_id,
        org_id=org.id,
        owner_user_id=ctx.user.id,
        storage_path=storage_path,
        original_filename=original_filename,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return audio_public(row)


@router.get("/audios", response_model=AudioListResponse)
def list_audios(
    include_hidden: bool = False,
    tag: str | None = None,
    owner_user_id: str | None = None,
    q: str | None = Query(None, max_length=LIBRARY_SEARCH_MAX_LEN),
    limit: int | None = Query(None, ge=1, le=LIBRARY_LIST_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> AudioListResponse:
    owner = lh.library_owner_filter(ctx, owner_user_id)
    rows = lh.list_filter(
        ctx, db, Audio, "audio", include_hidden, tag, owner, q, limit=limit, offset=offset
    )
    total = count_library_rows(
        ctx, db, Audio, "audio", include_hidden, tag, owner_user_id=owner, q=q
    )
    tag_map = batch_object_user_tags(db, ctx.user.id, "audio", [row.id for row in rows])
    badges = batch_share_badges(db, ctx, "audio", rows, user_tags_by_id=tag_map)
    derived = lh.audio_derived_info(db, ctx, [row.id for row in rows])
    return AudioListResponse(
        items=[
            AudioListItem.model_validate(
                {
                    **audio_public(row, badges.get(row.id)),
                    **derived.get(row.id, _derived_audio_defaults()),
                }
            )
            for row in rows
        ],
        total=total,
        hidden_count=lh.count_hidden_for_user(ctx, db, Audio, "audio"),
    )


@router.get("/audios/{audio_id}", response_model=AudioDetailResponse)
def get_audio(
    audio_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> AudioDetailResponse:
    row = db.get(Audio, audio_id)
    if row is None or not can_read_object(ctx, db, "audio", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    transcripts = db.scalars(
        select(Transcript).where(Transcript.source_audio_id == row.id).order_by(Transcript.created_at.desc())
    ).all()
    visible_transcripts = [
        item
        for item in transcripts
        if (
            can_read_object(ctx, db, "transcript", item.owner_user_id, item.org_id, item.id)
            or ctx.is_org_admin
        )
        and not is_hidden(db, ctx.user.id, "transcript", item.id)
    ]
    derived = lh.transcript_derived_info(db, ctx, [item.id for item in visible_transcripts])
    payload = audio_public(row, lh.share_badge(db, "audio", row.id, row.owner_user_id, ctx))
    payload["transcripts"] = [
        TranscriptListItem.model_validate(
            {
                **transcript_public(
                    item,
                    extra=lh.share_badge(db, "transcript", item.id, item.owner_user_id, ctx),
                    source_filename=row.original_filename,
                ),
                **derived.get(item.id, {"has_summary": False}),
                "has_tone_analytics": item.has_tone_analytics,
            }
        )
        for item in visible_transcripts
    ]
    payload["can_transcribe"] = get_storage().exists(row.storage_path)
    return AudioDetailResponse.model_validate(payload)


@router.get("/audios/{audio_id}/file")
def audio_file(
    audio_id: str,
    request: Request,
    download: bool = False,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
):
    row = db.get(Audio, audio_id)
    if row is None or not can_read_object(ctx, db, "audio", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    storage = get_storage()
    if not storage.exists(row.storage_path):
        ctx.raise_error(ErrorCode.not_found)
    return storage.download_response(
        row.storage_path,
        row.original_filename,
        download=download,
        range_header=request.headers.get("range"),
    )


@router.post("/audios/{audio_id}/hide")
def hide_audio(
    audio_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Audio, audio_id)
    if row is None or not can_read_object(ctx, db, "audio", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "audio", row.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="audio", object_id=row.id))
    return {"status": "ok"}


@router.post("/audios/{audio_id}/unhide")
def unhide_audio(
    audio_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Audio, audio_id)
    if row is None or not can_read_object(ctx, db, "audio", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    hidden = db.scalar(
        select(HiddenItem).where(
            HiddenItem.user_id == ctx.user.id,
            HiddenItem.object_type == "audio",
            HiddenItem.object_id == row.id,
        )
    )
    if hidden:
        db.delete(hidden)
    return {"status": "ok"}


@router.delete("/audios/{audio_id}")
def delete_audio(
    audio_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Audio, audio_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    ctx.require_org_admin()
    if ctx.org is None or row.org_id != ctx.org.id:
        ctx.raise_error(ErrorCode.not_found)
    write_audit(db, "audio.wipe", ctx, {"audio_id": row.id})
    hard_delete_audio(db, row)
    return {"status": "ok"}


@router.get("/transcripts", response_model=TranscriptListResponse)
def list_transcripts(
    include_hidden: bool = False,
    tag: str | None = None,
    owner_user_id: str | None = None,
    q: str | None = Query(None, max_length=LIBRARY_SEARCH_MAX_LEN),
    group_by: Literal["source"] | None = None,
    limit: int | None = Query(None, ge=1, le=LIBRARY_LIST_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_oauth_scope(SCOPE_TRANSCRIPTS_READ)),
) -> TranscriptListResponse:
    owner = lh.library_owner_filter(ctx, owner_user_id)
    hidden_count = lh.count_hidden_for_user(ctx, db, Transcript, "transcript")
    if group_by == "source":
        page_limit = limit if limit is not None else 50
        total = count_library_source_groups(
            ctx, db, Transcript, "transcript", include_hidden, tag, owner_user_id=owner, q=q
        )
        source_ids, rows = list_library_source_group_page(
            ctx,
            db,
            Transcript,
            "transcript",
            include_hidden,
            tag,
            owner_user_id=owner,
            q=q,
            limit=page_limit,
            offset=offset,
        )
        items = lh.transcript_list_items(db, ctx, rows)
        return TranscriptListResponse(
            groups=lh.transcript_source_groups(source_ids, items),
            total=total,
            hidden_count=hidden_count,
        )

    rows = lh.list_filter(
        ctx, db, Transcript, "transcript", include_hidden, tag, owner, q, limit=limit, offset=offset
    )
    total = count_library_rows(
        ctx, db, Transcript, "transcript", include_hidden, tag, owner_user_id=owner, q=q
    )
    return TranscriptListResponse(
        items=lh.transcript_list_items(db, ctx, rows),
        total=total,
        hidden_count=hidden_count,
    )


@router.get("/transcripts/{transcript_id}", response_model=TranscriptDetailResponse)
def get_transcript(
    transcript_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_oauth_scope(SCOPE_TRANSCRIPTS_READ)),
) -> TranscriptDetailResponse:
    row = db.get(Transcript, transcript_id)
    if row is None or not can_read_object(ctx, db, "transcript", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    stored = decode_transcript_payload(decrypt_str(row.utterances_encrypted, db))
    utterances = extract_utterances(stored)
    source_audio = db.get(Audio, row.source_audio_id) if row.source_audio_id else None
    summaries = db.scalars(
        select(Summary).where(Summary.source_transcript_id == row.id).order_by(Summary.created_at.desc())
    ).all()
    payload = transcript_public(
        row,
        utterances,
        {
            **lh.share_badge(db, "transcript", row.id, row.owner_user_id, ctx),
            **payload_tone_fields(stored),
        },
        source_filename=source_audio.original_filename if source_audio else None,
    )
    payload["summaries"] = [
        SummaryListItem.model_validate(
            summary_public(
                item,
                extra=lh.share_badge(db, "summary", item.id, item.owner_user_id, ctx),
                source_transcript=row,
                source_filename=source_audio.original_filename if source_audio else None,
            )
        )
        for item in summaries
        if (
            can_read_object(ctx, db, "summary", item.owner_user_id, item.org_id, item.id)
            or ctx.is_org_admin
        )
        and not is_hidden(db, ctx.user.id, "summary", item.id)
    ]
    return TranscriptDetailResponse.model_validate(payload)


@router.get("/transcripts/{transcript_id}/export")
def export_transcript(
    transcript_id: str,
    format: str = Query("txt", pattern="^(txt|json)$"),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
):
    row = db.get(Transcript, transcript_id)
    if row is None or not can_read_object(ctx, db, "transcript", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    stored = decode_transcript_payload(decrypt_str(row.utterances_encrypted, db))
    utterances = extract_utterances(stored)
    source_audio = db.get(Audio, row.source_audio_id) if row.source_audio_id else None
    stem = safe_filename(
        transcript_display_title(
            row,
            source_filename=source_audio.original_filename if source_audio else None,
        )
    )
    if format == "json":
        content = json.dumps(export_json_payload(stored), ensure_ascii=False, indent=2)
        return attachment_response(content, f"{stem}.json", "application/json")
    return attachment_response(utterances_to_text(utterances), f"{stem}.txt", "text/plain; charset=utf-8")


@router.post("/transcripts/{transcript_id}/hide")
def hide_transcript(
    transcript_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Transcript, transcript_id)
    if row is None or not can_read_object(ctx, db, "transcript", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "transcript", row.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="transcript", object_id=row.id))
    return {"status": "ok"}


@router.post("/transcripts/{transcript_id}/unhide")
def unhide_transcript(
    transcript_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Transcript, transcript_id)
    if row is None or not can_read_object(ctx, db, "transcript", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    hidden = db.scalar(
        select(HiddenItem).where(
            HiddenItem.user_id == ctx.user.id,
            HiddenItem.object_type == "transcript",
            HiddenItem.object_id == row.id,
        )
    )
    if hidden:
        db.delete(hidden)
    return {"status": "ok"}


@router.delete("/transcripts/{transcript_id}")
def delete_transcript(
    transcript_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Transcript, transcript_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    ctx.require_org_admin()
    if ctx.org is None or row.org_id != ctx.org.id:
        ctx.raise_error(ErrorCode.not_found)
    write_audit(db, "transcript.wipe", ctx, {"transcript_id": row.id})
    hard_delete_transcript(db, row)
    return {"status": "ok"}


@router.get("/summaries", response_model=SummaryListResponse)
def list_summaries(
    include_hidden: bool = False,
    tag: str | None = None,
    owner_user_id: str | None = None,
    q: str | None = Query(None, max_length=LIBRARY_SEARCH_MAX_LEN),
    group_by: Literal["source"] | None = None,
    limit: int | None = Query(None, ge=1, le=LIBRARY_LIST_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> SummaryListResponse:
    owner = lh.library_owner_filter(ctx, owner_user_id)
    hidden_count = lh.count_hidden_for_user(ctx, db, Summary, "summary")
    if group_by == "source":
        page_limit = limit if limit is not None else 50
        total = count_library_source_groups(
            ctx, db, Summary, "summary", include_hidden, tag, owner_user_id=owner, q=q
        )
        source_ids, rows = list_library_source_group_page(
            ctx,
            db,
            Summary,
            "summary",
            include_hidden,
            tag,
            owner_user_id=owner,
            q=q,
            limit=page_limit,
            offset=offset,
        )
        items = lh.summary_list_items(db, ctx, rows)
        return SummaryListResponse(
            groups=lh.summary_source_groups(source_ids, items),
            total=total,
            hidden_count=hidden_count,
        )

    rows = lh.list_filter(
        ctx, db, Summary, "summary", include_hidden, tag, owner, q, limit=limit, offset=offset
    )
    total = count_library_rows(
        ctx, db, Summary, "summary", include_hidden, tag, owner_user_id=owner, q=q
    )
    return SummaryListResponse(
        items=lh.summary_list_items(db, ctx, rows),
        total=total,
        hidden_count=hidden_count,
    )


@router.get("/summaries/{summary_id}", response_model=SummaryDetailResponse)
def get_summary(
    summary_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> SummaryDetailResponse:
    row = db.get(Summary, summary_id)
    if row is None or not can_read_object(ctx, db, "summary", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    body = decrypt_str(row.body_encrypted, db)
    source_transcript = db.get(Transcript, row.source_transcript_id) if row.source_transcript_id else None
    source_audio = (
        db.get(Audio, source_transcript.source_audio_id)
        if source_transcript and source_transcript.source_audio_id
        else None
    )
    return SummaryDetailResponse.model_validate(
        summary_public(
            row,
            body,
            lh.share_badge(db, "summary", row.id, row.owner_user_id, ctx),
            source_transcript=source_transcript,
            source_filename=source_audio.original_filename if source_audio else None,
        )
    )


@router.get("/summaries/{summary_id}/export")
def export_summary(
    summary_id: str,
    format: str = Query("md", pattern="^(md|txt)$"),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
):
    row = db.get(Summary, summary_id)
    if row is None or not can_read_object(ctx, db, "summary", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    source_transcript = db.get(Transcript, row.source_transcript_id) if row.source_transcript_id else None
    source_audio = (
        db.get(Audio, source_transcript.source_audio_id)
        if source_transcript and source_transcript.source_audio_id
        else None
    )
    body = unwrap_markdown_fence(decrypt_str(row.body_encrypted, db))
    ext = "md" if format == "md" else "txt"
    media = "text/markdown; charset=utf-8" if format == "md" else "text/plain; charset=utf-8"
    return attachment_response(
        body,
        f"{safe_filename(summary_display_title(row, source_transcript=source_transcript, source_filename=source_audio.original_filename if source_audio else None))}.{ext}",
        media,
    )


@router.post("/summaries/{summary_id}/hide")
def hide_summary(
    summary_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Summary, summary_id)
    if row is None or not can_read_object(ctx, db, "summary", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "summary", row.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="summary", object_id=row.id))
    return {"status": "ok"}


@router.post("/summaries/{summary_id}/unhide")
def unhide_summary(
    summary_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Summary, summary_id)
    if row is None or not can_read_object(ctx, db, "summary", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    hidden = db.scalar(
        select(HiddenItem).where(
            HiddenItem.user_id == ctx.user.id,
            HiddenItem.object_type == "summary",
            HiddenItem.object_id == row.id,
        )
    )
    if hidden:
        db.delete(hidden)
    return {"status": "ok"}


@router.patch("/transcripts/{transcript_id}")
def patch_transcript(
    transcript_id: str,
    body: TitlePatch,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    row = db.get(Transcript, transcript_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    if row.owner_user_id != ctx.user.id and not ctx.is_org_admin:
        ctx.raise_error(ErrorCode.forbidden)
    if ctx.org is None or row.org_id != ctx.org.id:
        ctx.raise_error(ErrorCode.not_found)
    row.title = body.title.strip()
    write_audit(db, "transcript.rename", ctx, {"transcript_id": row.id})
    source_audio = db.get(Audio, row.source_audio_id) if row.source_audio_id else None
    return transcript_public(
        row,
        extra=lh.share_badge(db, "transcript", row.id, row.owner_user_id, ctx),
        source_filename=source_audio.original_filename if source_audio else None,
    )


@router.patch("/summaries/{summary_id}")
def patch_summary(
    summary_id: str,
    body: SummaryPatch,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    row = db.get(Summary, summary_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    if row.owner_user_id != ctx.user.id and not ctx.is_org_admin:
        ctx.raise_error(ErrorCode.forbidden)
    if ctx.org is None or row.org_id != ctx.org.id:
        ctx.raise_error(ErrorCode.not_found)
    if body.body is None and body.title is None:
        ctx.raise_error(ErrorCode.validation_error)
    body_text = decrypt_str(row.body_encrypted, db)
    changed = False
    if body.title is not None:
        row.title = body.title.strip()
        changed = True
    if body.body is not None and body.body != body_text:
        row.body_encrypted = encrypt_str(body.body, db)
        row.edited = True
        body_text = body.body
        changed = True
    if changed:
        write_audit(db, "summary.update", ctx, {"summary_id": row.id})
    source_transcript = db.get(Transcript, row.source_transcript_id) if row.source_transcript_id else None
    source_audio = (
        db.get(Audio, source_transcript.source_audio_id)
        if source_transcript and source_transcript.source_audio_id
        else None
    )
    return summary_public(
        row,
        body_text,
        lh.share_badge(db, "summary", row.id, row.owner_user_id, ctx),
        source_transcript=source_transcript,
        source_filename=source_audio.original_filename if source_audio else None,
    )


@router.delete("/summaries/{summary_id}")
def delete_summary(
    summary_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Summary, summary_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    if row.owner_user_id != ctx.user.id and not ctx.is_org_admin:
        ctx.raise_error(ErrorCode.forbidden)
    if ctx.org is None or row.org_id != ctx.org.id:
        ctx.raise_error(ErrorCode.not_found)
    write_audit(db, "summary.delete", ctx, {"summary_id": row.id})
    hard_delete_summary(db, row)
    return {"status": "ok"}


@router.get("/shares")
def list_shares(
    object_type: str,
    object_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    lh.require_share_owner(db, object_type, object_id, ctx)
    rows = outgoing_shares(db, object_type, object_id)
    return {"items": lh.share_items(db, rows)}


@router.post("/shares")
def create_shares(
    body: ShareBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    obj = lh.require_share_owner(db, body.object_type, body.object_id, ctx)
    org, _ = ctx.require_org()
    created = []
    for uid in body.to_user_ids:
        if uid == ctx.user.id:
            continue
        from app.models import Membership

        membership = db.scalar(
            select(Membership).where(Membership.org_id == org.id, Membership.user_id == uid)
        )
        if membership is None:
            continue
        row = ensure_object_share(
            db,
            object_type=body.object_type,
            object_id=body.object_id,
            from_user_id=ctx.user.id,
            to_user_id=uid,
        )
        created.append(row.id)
        if body.object_type == "transcript" and obj.source_audio_id:
            audio = db.get(Audio, obj.source_audio_id)
            if (
                audio is not None
                and audio.org_id == org.id
                and audio.owner_user_id == ctx.user.id
            ):
                ensure_object_share(
                    db,
                    object_type="audio",
                    object_id=audio.id,
                    from_user_id=ctx.user.id,
                    to_user_id=uid,
                )
    return {"ids": created}


@router.delete("/shares/{share_id}")
def delete_share(
    share_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Share, share_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    if row.from_user_id != ctx.user.id and row.to_user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.forbidden)
    if row.object_type == "transcript":
        transcript = db.get(Transcript, row.object_id)
        if transcript and transcript.source_audio_id:
            revoke_paired_audio_share(
                db,
                audio_id=transcript.source_audio_id,
                from_user_id=row.from_user_id,
                to_user_id=row.to_user_id,
            )
    db.delete(row)
    return {"status": "ok"}


@router.get("/summaries/{summary_id}/public-link")
def get_summary_public_link(
    summary_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Summary, summary_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    lh.summary_public_link_access(row, ctx, owner_only=False)
    from app.services.public_links import get_link_for_summary, link_public_payload

    link = get_link_for_summary(db, row.id)
    if link is None:
        return {"link": None}
    return {"link": link_public_payload(link, db)}


@router.post("/summaries/{summary_id}/public-link")
def create_summary_public_link(
    summary_id: str,
    body: SummaryPublicLinkBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org()
    row = db.get(Summary, summary_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    lh.summary_public_link_access(row, ctx, owner_only=True)
    from app.services.public_links import create_or_update_link, link_public_payload

    try:
        link, _raw = create_or_update_link(
            db,
            summary=row,
            org=org,
            user=ctx.user,
            expires_in_days=body.expires_in_days,
            pin=body.pin,
        )
    except ApiError as exc:
        ctx.raise_error(exc.code, status_code=exc.status_code)
    write_audit(
        db,
        "summary.public_link.create",
        ctx,
        {"summary_id": row.id, "link_id": link.id, "pin_required": link.pin_hash is not None},
    )
    payload = link_public_payload(link, db)
    return {"link": payload}


@router.delete("/summaries/{summary_id}/public-link")
def delete_summary_public_link(
    summary_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Summary, summary_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    lh.summary_public_link_access(row, ctx, owner_only=False)
    from app.services.public_links import get_link_for_summary, revoke_link

    link = get_link_for_summary(db, row.id)
    if link is None:
        ctx.raise_error(ErrorCode.not_found)
    revoke_link(db, link)
    write_audit(db, "summary.public_link.revoke", ctx, {"summary_id": row.id, "link_id": link.id})
    return {"status": "ok"}
