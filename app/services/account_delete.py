"""Необратимое удаление аккаунта пользователя."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.errors import ApiError, ErrorCode
from app.i18n import t
from app.models import (
    ApiToken,
    Audio,
    HiddenItem,
    Membership,
    MfaChallenge,
    Organization,
    PasswordResetToken,
    RecoveryCode,
    Session as AuthSession,
    Share,
    Skill,
    Summary,
    Task,
    Transcript,
    UsageEvent,
    User,
)
from app.routers.auth import revoke_user_auth
from app.services.access import count_active_org_admins
from app.services.artifacts import hard_delete_audio, hard_delete_summary, hard_delete_transcript
from app.services.org_delete import delete_organization


def _active_org_member_candidates(
    db: Session, org_id: str, exclude_user_id: str
) -> list[tuple[User, Membership]]:
    rows: list[tuple[User, Membership]] = []
    for membership in db.scalars(select(Membership).where(Membership.org_id == org_id)).all():
        if membership.user_id == exclude_user_id:
            continue
        user = db.get(User, membership.user_id)
        if user is None or user.disabled_at is not None:
            continue
        rows.append((user, membership))
    rows.sort(key=lambda pair: pair[0].email.lower())
    return rows


def account_delete_preview(
    db: Session,
    user: User,
    membership: Membership | None,
    org: Organization | None,
) -> dict:
    requires_successor = False
    will_delete_org = False
    candidates: list[dict] = []
    if membership is not None and org is not None and membership.role == "org_admin":
        if count_active_org_admins(db, org.id, exclude_user_id=user.id) < 1:
            candidates = [
                {"id": u.id, "email": u.email, "role": m.role}
                for u, m in _active_org_member_candidates(db, org.id, user.id)
            ]
            if candidates:
                requires_successor = True
            else:
                will_delete_org = True
    return {
        "requires_successor": requires_successor,
        "will_delete_org": will_delete_org,
        "candidates": candidates,
    }


def _purge_user_owned_data(db: Session, user: User) -> None:
    for task in db.scalars(
        select(Task).where(Task.user_id == user.id, Task.status.in_(("queued", "running")))
    ).all():
        if task.status == "queued" and not task.worker_task_id:
            task.status = "error"
            task.error_code = "account_deleted"
        else:
            task.skip_persist = True
            task.skip_reason = "account_deleted"
    # Keep org billing rows; drop links to the deleted account and its tasks.
    db.execute(
        update(UsageEvent)
        .where(UsageEvent.user_id == user.id)
        .values(user_id=None, task_id=None)
    )
    db.execute(delete(Task).where(Task.user_id == user.id))
    for audio in list(db.scalars(select(Audio).where(Audio.owner_user_id == user.id)).all()):
        hard_delete_audio(db, audio)
    for transcript in list(db.scalars(select(Transcript).where(Transcript.owner_user_id == user.id)).all()):
        hard_delete_transcript(db, transcript)
    for summary in list(db.scalars(select(Summary).where(Summary.owner_user_id == user.id)).all()):
        hard_delete_summary(db, summary)
    db.execute(delete(Skill).where(Skill.owner_user_id == user.id))
    db.execute(
        delete(Share).where((Share.from_user_id == user.id) | (Share.to_user_id == user.id))
    )
    db.execute(delete(HiddenItem).where(HiddenItem.user_id == user.id))


def _purge_user_auth(db: Session, user_id: str) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.impersonate_user_id == user_id)
        .values(impersonate_user_id=None)
    )
    revoke_user_auth(db, user_id)
    db.execute(delete(ApiToken).where(ApiToken.user_id == user_id))
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
    db.execute(delete(MfaChallenge).where(MfaChallenge.user_id == user_id))
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))


def _promote_org_admin(db: Session, org_id: str, successor_user_id: str, locale: str) -> None:
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == successor_user_id)
    )
    user = db.get(User, successor_user_id)
    if membership is None or user is None or user.disabled_at is not None:
        raise ApiError(ErrorCode.validation_error, t(locale, ErrorCode.validation_error.value))
    membership.role = "org_admin"


def delete_user_account(
    db: Session,
    user: User,
    membership: Membership | None,
    org: Organization | None,
    *,
    successor_user_id: str | None,
    locale: str,
) -> dict:
    preview = account_delete_preview(db, user, membership, org)
    if preview["requires_successor"]:
        if not successor_user_id:
            raise ApiError(
                ErrorCode.org_admin_successor_required,
                t(locale, ErrorCode.org_admin_successor_required.value),
            )
        allowed = {row["id"] for row in preview["candidates"]}
        if successor_user_id not in allowed:
            raise ApiError(ErrorCode.validation_error, t(locale, ErrorCode.validation_error.value))
        assert org is not None
        _promote_org_admin(db, org.id, successor_user_id, locale)

    if preview["will_delete_org"]:
        assert org is not None
        org_id = org.id
        delete_organization(db, org)
        return {"status": "ok", "org_deleted": True, "org_id": org_id}

    _purge_user_owned_data(db, user)
    _purge_user_auth(db, user.id)
    if membership is not None:
        db.delete(membership)
    db.delete(user)
    return {"status": "ok", "org_deleted": False}
