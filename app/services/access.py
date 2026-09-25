"""Правила видимости, последний org admin, шары."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import AuthContext
from app.errors import ApiError, ErrorCode
from app.i18n import t
from app.models import HiddenItem, Membership, Share, User, new_id
from app.timeutil import utcnow


def count_active_org_admins(db: Session, org_id: str, exclude_user_id: str | None = None) -> int:
    q = (
        select(func.count())
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.org_id == org_id,
            Membership.role == "org_admin",
            User.disabled_at.is_(None),
        )
    )
    if exclude_user_id:
        q = q.where(Membership.user_id != exclude_user_id)
    return int(db.scalar(q) or 0)


def guard_last_org_admin(db: Session, org_id: str, user_id: str, locale: str) -> None:
    if count_active_org_admins(db, org_id, exclude_user_id=user_id) < 1:
        raise ApiError(ErrorCode.last_org_admin, t(locale, ErrorCode.last_org_admin.value))


def is_shared_with(db: Session, object_type: str, object_id: str, user_id: str) -> Share | None:
    return db.scalar(
        select(Share).where(
            Share.object_type == object_type,
            Share.object_id == object_id,
            Share.to_user_id == user_id,
        )
    )


def is_hidden(db: Session, user_id: str, object_type: str, object_id: str) -> bool:
    row = db.scalar(
        select(HiddenItem).where(
            HiddenItem.user_id == user_id,
            HiddenItem.object_type == object_type,
            HiddenItem.object_id == object_id,
        )
    )
    return row is not None


def can_read_object(
    ctx: AuthContext,
    db: Session,
    object_type: str,
    owner_user_id: str,
    org_id: str,
    object_id: str,
) -> bool:
    if ctx.org is None or ctx.org.id != org_id:
        return ctx.is_instance_admin
    if ctx.is_org_admin:
        return True
    if owner_user_id == ctx.user.id:
        return True
    return is_shared_with(db, object_type, object_id, ctx.user.id) is not None


def can_use_audio(ctx: AuthContext, db: Session, audio) -> bool:
    return can_read_object(ctx, db, "audio", audio.owner_user_id, audio.org_id, audio.id)


def can_use_transcript(ctx: AuthContext, db: Session, transcript) -> bool:
    return can_read_object(
        ctx, db, "transcript", transcript.owner_user_id, transcript.org_id, transcript.id
    )


def outgoing_shares(db: Session, object_type: str, object_id: str) -> list[Share]:
    return list(
        db.scalars(
            select(Share).where(Share.object_type == object_type, Share.object_id == object_id)
        )
    )


def ensure_object_share(
    db: Session,
    *,
    object_type: str,
    object_id: str,
    from_user_id: str,
    to_user_id: str,
) -> Share:
    existing = is_shared_with(db, object_type, object_id, to_user_id)
    if existing:
        return existing
    row = Share(
        id=new_id(),
        object_type=object_type,
        object_id=object_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def revoke_paired_audio_share(
    db: Session,
    *,
    audio_id: str,
    from_user_id: str,
    to_user_id: str,
) -> None:
    row = db.scalar(
        select(Share).where(
            Share.object_type == "audio",
            Share.object_id == audio_id,
            Share.from_user_id == from_user_id,
            Share.to_user_id == to_user_id,
        )
    )
    if row is not None:
        db.delete(row)
