"""Library HTTP routes: shares."""

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
from app.schemas.shares import OkStatusResponse, ShareCreateResponse, ShareListResponse
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


@router.get("/shares", response_model=ShareListResponse)
def list_shares(
    object_type: str,
    object_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> ShareListResponse:
    lh.require_share_owner(db, object_type, object_id, ctx)
    rows = outgoing_shares(db, object_type, object_id)
    return ShareListResponse(items=lh.share_items(db, rows))


@router.post("/shares", response_model=ShareCreateResponse)
def create_shares(
    body: ShareBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> ShareCreateResponse:
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
    return ShareCreateResponse(ids=created)


@router.delete("/shares/{share_id}", response_model=OkStatusResponse)
def delete_share(
    share_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
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
    return OkStatusResponse()

