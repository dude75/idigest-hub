"""Library HTTP routes: transcripts."""

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
    can_delete_library_object,
    can_read_object,
    ensure_library_readable,
    ensure_object_share,
    is_hidden,
    is_shared_with,
    outgoing_shares,
    revoke_paired_audio_share,
)
from app.services.artifact_impact import compute_transcript_delete_impact
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
    LibraryArtifactDeleteImpactResponse,
    _derived_audio_defaults,
)
from app.services.billing import upload_limit
from app.timeutil import utcnow
from app.services import library_helpers as lh

from app.routers.library._router import router


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
    if not ensure_library_readable(ctx, db, row, "transcript", audit=True):
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
    if not ensure_library_readable(ctx, db, row, "transcript", audit=True):
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


@router.post("/transcripts/{transcript_id}/hide", response_model=OkStatusResponse)
def hide_transcript(
    transcript_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
    row = db.get(Transcript, transcript_id)
    if row is None or not can_read_object(ctx, db, "transcript", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "transcript", row.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="transcript", object_id=row.id))
    return OkStatusResponse()


@router.post("/transcripts/{transcript_id}/unhide", response_model=OkStatusResponse)
def unhide_transcript(
    transcript_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
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
    return OkStatusResponse()


@router.get("/transcripts/{transcript_id}/delete-impact", response_model=LibraryArtifactDeleteImpactResponse)
def transcript_delete_impact(
    transcript_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> LibraryArtifactDeleteImpactResponse:
    row = db.get(Transcript, transcript_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    if not can_delete_library_object(ctx, row.owner_user_id, row.org_id):
        ctx.raise_error(ErrorCode.forbidden)
    payload = compute_transcript_delete_impact(db, row)
    return LibraryArtifactDeleteImpactResponse.model_validate(payload)


@router.delete("/transcripts/{transcript_id}", response_model=OkStatusResponse)
def delete_transcript(
    transcript_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
    row = db.get(Transcript, transcript_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    if not can_delete_library_object(ctx, row.owner_user_id, row.org_id):
        ctx.raise_error(ErrorCode.forbidden)
    write_audit(db, "transcript.wipe", ctx, {"transcript_id": row.id})
    hard_delete_transcript(db, row)
    return OkStatusResponse()


@router.patch("/transcripts/{transcript_id}", response_model=TranscriptListItem)
def patch_transcript(
    transcript_id: str,
    body: TitlePatch,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> TranscriptListItem:
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
    return TranscriptListItem.model_validate(
        transcript_public(
            row,
            extra=lh.share_badge(db, "transcript", row.id, row.owner_user_id, ctx),
            source_filename=source_audio.original_filename if source_audio else None,
        )
    )

