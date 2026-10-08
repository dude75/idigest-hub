"""Library HTTP routes: audios."""

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
    ensure_library_readable,
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
from app.schemas.common import OkStatusResponse
from app.schemas.library import (
    ShareBody,
    TitlePatch,
    SummaryPatch,
    SummaryPublicLinkBody,
    AudioCreatedResponse,
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


@router.post("/audios", response_model=AudioCreatedResponse)
async def upload_audio(
    request: Request,
    file: UploadFile,
    from_microphone: bool = Form(False),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> AudioCreatedResponse:
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
    from app.services.source_tags import tag_audio_file_upload
    from app.services.user_tags import object_user_tags

    tag_audio_file_upload(db, user_id=ctx.user.id, audio_id=audio_id, from_microphone=from_microphone)
    return AudioCreatedResponse.model_validate(
        audio_public(row, {"user_tags": object_user_tags(db, ctx.user.id, "audio", audio_id)})
    )


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
    if not ensure_library_readable(ctx, db, row, "audio", audit=True):
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
    if not ensure_library_readable(ctx, db, row, "audio", audit=True):
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


@router.post("/audios/{audio_id}/hide", response_model=OkStatusResponse)
def hide_audio(
    audio_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
    row = db.get(Audio, audio_id)
    if row is None or not can_read_object(ctx, db, "audio", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "audio", row.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="audio", object_id=row.id))
    return OkStatusResponse()


@router.post("/audios/{audio_id}/unhide", response_model=OkStatusResponse)
def unhide_audio(
    audio_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
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
    return OkStatusResponse()


@router.delete("/audios/{audio_id}", response_model=OkStatusResponse)
def delete_audio(
    audio_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
    row = db.get(Audio, audio_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    ctx.require_org_admin()
    if ctx.org is None or row.org_id != ctx.org.id:
        ctx.raise_error(ErrorCode.not_found)
    write_audit(db, "audio.wipe", ctx, {"audio_id": row.id})
    hard_delete_audio(db, row)
    return OkStatusResponse()

