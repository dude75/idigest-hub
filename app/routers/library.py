"""Аудио, транскрипты, саммари, hide/wipe, шары (ТЗ §7–8)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import ALLOWED_AUDIO_SUFFIXES, MAX_UPLOAD_BYTES_CAP
from app.crypto import decrypt_str, encrypt_str
from app.db import get_session
from app.deps import AuthContext, require_auth
from app.errors import ErrorCode
from app.models import Audio, HiddenItem, Share, Summary, Transcript, User, new_id
from app.presenters import audio_public, summary_public, transcript_public
from app.services.access import can_read_object, is_hidden, is_shared_with, outgoing_shares
from app.services.artifacts import hard_delete_audio, hard_delete_summary, hard_delete_transcript
from app.services.dispatcher import utterances_to_text
from app.services.export import attachment_response, safe_filename
from app.services.audit import write_audit
from app.services.billing import upload_limit
from app.timeutil import utcnow

router = APIRouter()


class ShareBody(BaseModel):
    object_type: str
    object_id: str
    to_user_ids: list[str]


class SummaryPatch(BaseModel):
    body: str


def _share_items(db: Session, rows: list[Share]) -> list[dict]:
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


def _share_badge(db: Session, object_type: str, object_id: str, owner_id: str, ctx: AuthContext) -> dict:
    extra: dict = {}
    if owner_id == ctx.user.id:
        outgoing = outgoing_shares(db, object_type, object_id)
        extra["shared_with"] = [row.to_user_id for row in outgoing]
        extra["shares"] = _share_items(db, outgoing)
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
    return extra


def _list_filter(
    ctx: AuthContext,
    db: Session,
    model,
    object_type: str,
    include_hidden: bool,
):
    org, membership = ctx.require_org()
    rows = list(db.scalars(select(model).where(model.org_id == org.id).order_by(model.created_at.desc())).all())
    visible = []
    for row in rows:
        owner = row.owner_user_id
        if membership.role == "org_admin":
            visible.append(row)
            continue
        own = owner == ctx.user.id
        shared = is_shared_with(db, object_type, row.id, ctx.user.id) is not None
        if not own and not shared:
            continue
        if own and not include_hidden and is_hidden(db, ctx.user.id, object_type, row.id):
            continue
        visible.append(row)
    return visible


@router.post("/audios")
async def upload_audio(
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
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
    dest_dir = Path(get_settings().DATA_DIR) / "uploads" / audio_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"original{suffix}"
    size = 0
    try:
        with dest.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    handle.close()
                    dest.unlink(missing_ok=True)
                    ctx.raise_error(ErrorCode.payload_too_large)
                handle.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    row = Audio(
        id=audio_id,
        org_id=org.id,
        owner_user_id=ctx.user.id,
        storage_path=str(dest),
        original_filename=file.filename or dest.name,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return audio_public(row)


@router.get("/audios")
def list_audios(
    include_hidden: bool = False,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    rows = _list_filter(ctx, db, Audio, "audio", include_hidden)
    return {
        "items": [
            audio_public(row, _share_badge(db, "audio", row.id, row.owner_user_id, ctx)) for row in rows
        ]
    }


@router.get("/audios/{audio_id}")
def get_audio(
    audio_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Audio, audio_id)
    if row is None or not can_read_object(ctx, db, "audio", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    transcripts = db.scalars(
        select(Transcript).where(Transcript.source_audio_id == row.id).order_by(Transcript.created_at.desc())
    ).all()
    payload = audio_public(row, _share_badge(db, "audio", row.id, row.owner_user_id, ctx))
    payload["transcripts"] = [
        transcript_public(
            item,
            extra=_share_badge(db, "transcript", item.id, item.owner_user_id, ctx),
            source_filename=row.original_filename,
        )
        for item in transcripts
        if can_read_object(ctx, db, "transcript", item.owner_user_id, item.org_id, item.id)
        or ctx.is_org_admin
    ]
    payload["can_transcribe"] = Path(row.storage_path).is_file()
    return payload


@router.get("/audios/{audio_id}/file")
def audio_file(
    audio_id: str,
    download: bool = False,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
):
    row = db.get(Audio, audio_id)
    if row is None or not can_read_object(ctx, db, "audio", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    path = Path(row.storage_path)
    if not path.is_file():
        ctx.raise_error(ErrorCode.not_found)
    headers = {}
    if download:
        headers["Content-Disposition"] = (
            f'attachment; filename="{safe_filename(row.original_filename)}"'
        )
    return FileResponse(path, filename=row.original_filename, headers=headers)


@router.post("/audios/{audio_id}/hide")
def hide_audio(
    audio_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Audio, audio_id)
    if row is None or row.owner_user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "audio", row.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="audio", object_id=row.id))
    return {"status": "ok"}


@router.post("/audios/{audio_id}/unhide")
def unhide_audio(
    audio_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Audio, audio_id)
    if row is None or row.owner_user_id != ctx.user.id:
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
    audio_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
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


def _audio_filenames(db: Session, audio_ids: set[str | None]) -> dict[str, str]:
    ids = [audio_id for audio_id in audio_ids if audio_id]
    if not ids:
        return {}
    return {
        audio.id: audio.original_filename
        for audio in db.scalars(select(Audio).where(Audio.id.in_(ids))).all()
    }


@router.get("/transcripts")
def list_transcripts(
    include_hidden: bool = False,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    rows = _list_filter(ctx, db, Transcript, "transcript", include_hidden)
    filenames = _audio_filenames(db, {row.source_audio_id for row in rows})
    return {
        "items": [
            transcript_public(
                row,
                extra=_share_badge(db, "transcript", row.id, row.owner_user_id, ctx),
                source_filename=filenames.get(row.source_audio_id) if row.source_audio_id else None,
            )
            for row in rows
        ]
    }


@router.get("/transcripts/{transcript_id}")
def get_transcript(
    transcript_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Transcript, transcript_id)
    if row is None or not can_read_object(ctx, db, "transcript", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    utterances = json.loads(decrypt_str(row.utterances_encrypted))
    source_audio = db.get(Audio, row.source_audio_id) if row.source_audio_id else None
    summaries = db.scalars(
        select(Summary).where(Summary.source_transcript_id == row.id).order_by(Summary.created_at.desc())
    ).all()
    payload = transcript_public(
        row,
        utterances,
        _share_badge(db, "transcript", row.id, row.owner_user_id, ctx),
        source_filename=source_audio.original_filename if source_audio else None,
    )
    payload["summaries"] = [
        summary_public(item, extra=_share_badge(db, "summary", item.id, item.owner_user_id, ctx))
        for item in summaries
        if can_read_object(ctx, db, "summary", item.owner_user_id, item.org_id, item.id) or ctx.is_org_admin
    ]
    return payload


@router.get("/transcripts/{transcript_id}/export")
def export_transcript(
    transcript_id: str,
    format: str = Query("txt", pattern="^(txt|json)$"),
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
):
    row = db.get(Transcript, transcript_id)
    if row is None or not can_read_object(ctx, db, "transcript", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    utterances = json.loads(decrypt_str(row.utterances_encrypted))
    source_audio = db.get(Audio, row.source_audio_id) if row.source_audio_id else None
    base = source_audio.original_filename if source_audio else f"transcript-{row.id[:8]}"
    stem = Path(base).stem
    if format == "json":
        content = json.dumps(utterances, ensure_ascii=False, indent=2)
        return attachment_response(content, f"{stem}.json", "application/json")
    return attachment_response(utterances_to_text(utterances), f"{stem}.txt", "text/plain; charset=utf-8")


@router.post("/transcripts/{transcript_id}/hide")
def hide_transcript(
    transcript_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Transcript, transcript_id)
    if row is None or row.owner_user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "transcript", row.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="transcript", object_id=row.id))
    return {"status": "ok"}


@router.post("/transcripts/{transcript_id}/unhide")
def unhide_transcript(
    transcript_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Transcript, transcript_id)
    if row is None or row.owner_user_id != ctx.user.id:
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
    transcript_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
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


@router.get("/summaries")
def list_summaries(
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    rows = _list_filter(ctx, db, Summary, "summary", include_hidden=True)
    return {
        "items": [
            summary_public(row, extra=_share_badge(db, "summary", row.id, row.owner_user_id, ctx))
            for row in rows
        ]
    }


@router.get("/summaries/{summary_id}")
def get_summary(
    summary_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Summary, summary_id)
    if row is None or not can_read_object(ctx, db, "summary", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    body = decrypt_str(row.body_encrypted)
    return summary_public(row, body, _share_badge(db, "summary", row.id, row.owner_user_id, ctx))


@router.get("/summaries/{summary_id}/export")
def export_summary(
    summary_id: str,
    format: str = Query("md", pattern="^(md|txt)$"),
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
):
    row = db.get(Summary, summary_id)
    if row is None or not can_read_object(ctx, db, "summary", row.owner_user_id, row.org_id, row.id):
        ctx.raise_error(ErrorCode.not_found)
    body = decrypt_str(row.body_encrypted)
    ext = "md" if format == "md" else "txt"
    media = "text/markdown; charset=utf-8" if format == "md" else "text/plain; charset=utf-8"
    return attachment_response(body, f"summary-{row.id[:8]}.{ext}", media)


@router.patch("/summaries/{summary_id}")
def patch_summary(
    summary_id: str,
    body: SummaryPatch,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    row = db.get(Summary, summary_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    if row.owner_user_id != ctx.user.id and not ctx.is_org_admin:
        ctx.raise_error(ErrorCode.forbidden)
    if ctx.org is None or row.org_id != ctx.org.id:
        ctx.raise_error(ErrorCode.not_found)
    current = decrypt_str(row.body_encrypted)
    if body.body != current:
        row.body_encrypted = encrypt_str(body.body)
        row.edited = True
        write_audit(db, "summary.update", ctx, {"summary_id": row.id})
    return summary_public(row, body.body, _share_badge(db, "summary", row.id, row.owner_user_id, ctx))


@router.delete("/summaries/{summary_id}")
def delete_summary(
    summary_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
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


def _owner_of(db: Session, object_type: str, object_id: str):
    model = {"audio": Audio, "transcript": Transcript, "summary": Summary, "skill": None}[object_type]
    if object_type == "skill":
        from app.models import Skill

        return db.get(Skill, object_id)
    return db.get(model, object_id)


def _require_share_owner(
    db: Session, object_type: str, object_id: str, ctx: AuthContext
):
    if object_type not in {"audio", "transcript", "summary", "skill"}:
        ctx.raise_error(ErrorCode.validation_error)
    obj = _owner_of(db, object_type, object_id)
    if obj is None:
        ctx.raise_error(ErrorCode.not_found)
    if object_type == "skill":
        if obj.scope != "self" or obj.owner_user_id != ctx.user.id:
            ctx.raise_error(ErrorCode.forbidden)
    elif obj.owner_user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.forbidden)
    return obj


@router.get("/shares")
def list_shares(
    object_type: str,
    object_id: str,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _require_share_owner(db, object_type, object_id, ctx)
    rows = outgoing_shares(db, object_type, object_id)
    return {"items": _share_items(db, rows)}


@router.post("/shares")
def create_shares(
    body: ShareBody, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    obj = _require_share_owner(db, body.object_type, body.object_id, ctx)
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
        existing = is_shared_with(db, body.object_type, body.object_id, uid)
        if existing:
            created.append(existing.id)
            continue
        row = Share(
            id=new_id(),
            object_type=body.object_type,
            object_id=body.object_id,
            from_user_id=ctx.user.id,
            to_user_id=uid,
            created_at=utcnow(),
        )
        db.add(row)
        db.flush()
        created.append(row.id)
    return {"ids": created}


@router.delete("/shares/{share_id}")
def delete_share(
    share_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    row = db.get(Share, share_id)
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    if row.from_user_id != ctx.user.id and row.to_user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.forbidden)
    db.delete(row)
    return {"status": "ok"}
