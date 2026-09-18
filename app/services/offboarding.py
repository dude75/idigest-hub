"""Офбординг пользователя: перенос или wipe (ТЗ §4)."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import (
    ApiToken,
    Audio,
    HiddenItem,
    Session as AuthSession,
    Share,
    Skill,
    Summary,
    Task,
    Transcript,
    User,
)
from app.services.artifacts import hard_delete_audio, hard_delete_summary, hard_delete_transcript


def transfer_user(db: Session, user: User, target: User) -> None:
    db.execute(update(Audio).where(Audio.owner_user_id == user.id).values(owner_user_id=target.id))
    db.execute(update(Transcript).where(Transcript.owner_user_id == user.id).values(owner_user_id=target.id))
    db.execute(update(Summary).where(Summary.owner_user_id == user.id).values(owner_user_id=target.id))
    db.execute(
        update(Skill)
        .where(Skill.owner_user_id == user.id, Skill.scope == "self")
        .values(owner_user_id=target.id)
    )
    incoming = list(db.scalars(select(Share).where(Share.to_user_id == user.id)).all())
    for share in incoming:
        dup = db.scalar(
            select(Share).where(
                Share.object_type == share.object_type,
                Share.object_id == share.object_id,
                Share.to_user_id == target.id,
            )
        )
        if dup is not None:
            db.delete(share)
        else:
            share.to_user_id = target.id
    outgoing = list(db.scalars(select(Share).where(Share.from_user_id == user.id)).all())
    for share in outgoing:
        dup = db.scalar(
            select(Share).where(
                Share.object_type == share.object_type,
                Share.object_id == share.object_id,
                Share.to_user_id == share.to_user_id,
                Share.id != share.id,
            )
        )
        if dup is not None:
            db.delete(share)
        else:
            share.from_user_id = target.id
    db.execute(update(Task).where(Task.user_id == user.id).values(user_id=target.id))
    db.execute(delete(HiddenItem).where(HiddenItem.user_id == user.id))
    db.execute(delete(ApiToken).where(ApiToken.user_id == user.id))
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))


def wipe_user_content(db: Session, user: User) -> None:
    for task in db.scalars(
        select(Task).where(Task.user_id == user.id, Task.status.in_(("queued", "running")))
    ).all():
        if task.status == "queued" and not task.worker_task_id:
            task.status = "error"
            task.error_code = "account_wiped"
        else:
            task.skip_persist = True
            task.skip_reason = "account_wiped"
    for audio in list(db.scalars(select(Audio).where(Audio.owner_user_id == user.id)).all()):
        hard_delete_audio(db, audio)
    for transcript in list(db.scalars(select(Transcript).where(Transcript.owner_user_id == user.id)).all()):
        hard_delete_transcript(db, transcript)
    for summary in list(db.scalars(select(Summary).where(Summary.owner_user_id == user.id)).all()):
        hard_delete_summary(db, summary)
    db.execute(delete(Skill).where(Skill.owner_user_id == user.id, Skill.scope == "self"))
    db.execute(
        delete(Share).where((Share.from_user_id == user.id) | (Share.to_user_id == user.id))
    )
    db.execute(delete(HiddenItem).where(HiddenItem.user_id == user.id))
    db.execute(delete(ApiToken).where(ApiToken.user_id == user.id))
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
