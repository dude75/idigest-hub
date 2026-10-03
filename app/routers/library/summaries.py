"""Library HTTP routes: summaries."""

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
