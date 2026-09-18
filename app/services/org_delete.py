"""Каскадное удаление организации и всех связанных данных."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

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
    SummaryPublicLink,
    Task,
    Transcript,
    UsageEvent,
    User,
)
from app.routers.auth import revoke_user_auth
from app.services.artifacts import hard_delete_audio, hard_delete_summary, hard_delete_transcript


def _cancel_active_org_tasks(db: Session, org_id: str) -> None:
    for task in db.scalars(
        select(Task).where(Task.org_id == org_id, Task.status.in_(("queued", "running")))
    ):
        if task.status == "queued" and not task.worker_task_id:
            task.status = "error"
            task.error_code = "org_deleted"
        else:
            task.skip_persist = True
            task.skip_reason = "org_deleted"


def _delete_org_member(db: Session, user: User, membership: Membership) -> None:
    if user.is_instance_admin:
        return
    db.execute(
        update(AuthSession)
        .where(AuthSession.impersonate_user_id == user.id)
        .values(impersonate_user_id=None)
    )
    revoke_user_auth(db, user.id)
    db.execute(delete(ApiToken).where(ApiToken.user_id == user.id))
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    db.execute(delete(MfaChallenge).where(MfaChallenge.user_id == user.id))
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    db.execute(delete(Skill).where(Skill.owner_user_id == user.id, Skill.scope == "self"))
    db.execute(
        delete(Share).where((Share.from_user_id == user.id) | (Share.to_user_id == user.id))
    )
    db.execute(delete(HiddenItem).where(HiddenItem.user_id == user.id))
    db.delete(membership)
    db.delete(user)


def delete_organization(db: Session, org: Organization) -> None:
    org_id = org.id

    _cancel_active_org_tasks(db, org_id)

    for audio in list(db.scalars(select(Audio).where(Audio.org_id == org_id)).all()):
        hard_delete_audio(db, audio)
    for transcript in list(db.scalars(select(Transcript).where(Transcript.org_id == org_id)).all()):
        hard_delete_transcript(db, transcript)
    for summary in list(db.scalars(select(Summary).where(Summary.org_id == org_id)).all()):
        hard_delete_summary(db, summary)

    db.execute(delete(Skill).where(Skill.org_id == org_id))
    db.execute(delete(SummaryPublicLink).where(SummaryPublicLink.org_id == org_id))
    db.execute(delete(UsageEvent).where(UsageEvent.org_id == org_id))
    db.execute(delete(Task).where(Task.org_id == org_id))

    for membership in list(db.scalars(select(Membership).where(Membership.org_id == org_id)).all()):
        user = db.get(User, membership.user_id)
        if user is None:
            db.delete(membership)
            continue
        _delete_org_member(db, user, membership)

    db.execute(
        delete(HiddenItem).where(HiddenItem.object_type == "org", HiddenItem.object_id == org_id)
    )
    db.delete(org)
