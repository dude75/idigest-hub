"""Личные теги пользователя на объектах библиотеки (без ACL)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, ErrorCode
from app.models import UserTag, UserTagLink, new_id
from app.timeutil import utcnow

LIBRARY_OBJECT_TYPES = frozenset({"audio", "transcript", "summary"})
MAX_TAG_NAME_LEN = 64
_MAX_TAGS_PER_OBJECT = 32


def normalize_tag_name(raw: str) -> str:
    name = " ".join(raw.strip().split())
    if not name or len(name) > MAX_TAG_NAME_LEN:
        raise ApiError(ErrorCode.validation_error)
    return name


def tag_name_key(name: str) -> str:
    return name.casefold()


def resolve_user_tag(db: Session, user_id: str, tag_ref: str) -> UserTag | None:
    ref = tag_ref.strip()
    if not ref:
        return None
    if _looks_like_uuid(ref):
        row = db.scalar(select(UserTag).where(UserTag.id == ref, UserTag.user_id == user_id))
        if row is not None:
            return row
    key = tag_name_key(ref)
    return db.scalar(select(UserTag).where(UserTag.user_id == user_id, UserTag.name_key == key))


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def get_or_create_tag(db: Session, user_id: str, raw_name: str) -> UserTag:
    name = normalize_tag_name(raw_name)
    key = tag_name_key(name)
    existing = db.scalar(select(UserTag).where(UserTag.user_id == user_id, UserTag.name_key == key))
    if existing is not None:
        return existing
    row = UserTag(id=new_id(), user_id=user_id, name=name, name_key=key, created_at=utcnow())
    db.add(row)
    db.flush()
    return row


def tag_public(row: UserTag, *, usage_count: int | None = None) -> dict:
    payload = {"id": row.id, "name": row.name}
    if usage_count is not None:
        payload["usage_count"] = usage_count
    return payload


def list_user_tags(db: Session, user_id: str) -> list[dict]:
    counts = dict(
        db.execute(
            select(UserTagLink.tag_id, func.count())
            .where(UserTagLink.user_id == user_id)
            .group_by(UserTagLink.tag_id)
        ).all()
    )
    rows = list(
        db.scalars(select(UserTag).where(UserTag.user_id == user_id).order_by(UserTag.name_key)).all()
    )
    return [tag_public(row, usage_count=int(counts.get(row.id, 0))) for row in rows]


def object_user_tags(db: Session, user_id: str, object_type: str, object_id: str) -> list[dict]:
    rows = db.scalars(
        select(UserTag)
        .join(UserTagLink, UserTagLink.tag_id == UserTag.id)
        .where(
            UserTagLink.user_id == user_id,
            UserTagLink.object_type == object_type,
            UserTagLink.object_id == object_id,
        )
        .order_by(UserTag.name_key)
    ).all()
    return [tag_public(row) for row in rows]


def batch_object_user_tags(
    db: Session, user_id: str, object_type: str, object_ids: list[str]
) -> dict[str, list[dict]]:
    if not object_ids:
        return {}
    pairs = db.execute(
        select(UserTagLink.object_id, UserTag)
        .join(UserTag, UserTag.id == UserTagLink.tag_id)
        .where(
            UserTagLink.user_id == user_id,
            UserTagLink.object_type == object_type,
            UserTagLink.object_id.in_(object_ids),
        )
        .order_by(UserTag.name_key)
    ).all()
    result: dict[str, list[dict]] = {oid: [] for oid in object_ids}
    for object_id, tag in pairs:
        result.setdefault(object_id, []).append(tag_public(tag))
    return result


def object_ids_with_tag(db: Session, user_id: str, object_type: str, tag_id: str) -> set[str]:
    rows = db.scalars(
        select(UserTagLink.object_id).where(
            UserTagLink.user_id == user_id,
            UserTagLink.object_type == object_type,
            UserTagLink.tag_id == tag_id,
        )
    ).all()
    return set(rows)


def set_object_tags(
    db: Session,
    *,
    user_id: str,
    object_type: str,
    object_id: str,
    tag_names: list[str],
) -> list[dict]:
    if object_type not in LIBRARY_OBJECT_TYPES:
        raise ApiError(ErrorCode.validation_error)
    cleaned: list[str] = []
    seen_keys: set[str] = set()
    for raw in tag_names:
        name = normalize_tag_name(raw)
        key = tag_name_key(name)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        cleaned.append(name)
    if len(cleaned) > _MAX_TAGS_PER_OBJECT:
        raise ApiError(ErrorCode.validation_error)

    db.execute(
        delete(UserTagLink).where(
            UserTagLink.user_id == user_id,
            UserTagLink.object_type == object_type,
            UserTagLink.object_id == object_id,
        )
    )
    for name in cleaned:
        tag = get_or_create_tag(db, user_id, name)
        db.add(
            UserTagLink(
                id=new_id(),
                user_id=user_id,
                tag_id=tag.id,
                object_type=object_type,
                object_id=object_id,
                created_at=utcnow(),
            )
        )
    db.flush()
    _prune_unused_tags(db, user_id)
    return object_user_tags(db, user_id, object_type, object_id)


def rename_user_tag(db: Session, user_id: str, tag_id: str, raw_name: str) -> dict:
    row = db.get(UserTag, tag_id)
    if row is None or row.user_id != user_id:
        raise ApiError(ErrorCode.not_found)
    name = normalize_tag_name(raw_name)
    key = tag_name_key(name)
    if key != row.name_key:
        conflict = db.scalar(
            select(UserTag).where(UserTag.user_id == user_id, UserTag.name_key == key, UserTag.id != tag_id)
        )
        if conflict is not None:
            raise ApiError(ErrorCode.validation_error)
    row.name = name
    row.name_key = key
    db.flush()
    usage = int(
        db.scalar(
            select(func.count())
            .select_from(UserTagLink)
            .where(UserTagLink.user_id == user_id, UserTagLink.tag_id == tag_id)
        )
        or 0
    )
    return tag_public(row, usage_count=usage)


def delete_user_tag(db: Session, user_id: str, tag_id: str) -> None:
    row = db.get(UserTag, tag_id)
    if row is None or row.user_id != user_id:
        raise ApiError(ErrorCode.not_found)
    db.execute(delete(UserTagLink).where(UserTagLink.tag_id == tag_id, UserTagLink.user_id == user_id))
    db.delete(row)


def wipe_object_tag_links(db: Session, object_type: str, object_id: str) -> None:
    tag_ids = list(
        db.scalars(
            select(UserTagLink.tag_id).where(
                UserTagLink.object_type == object_type, UserTagLink.object_id == object_id
            )
        ).all()
    )
    db.execute(
        delete(UserTagLink).where(
            UserTagLink.object_type == object_type, UserTagLink.object_id == object_id
        )
    )
    _prune_tag_ids(db, tag_ids)


def _prune_tag_ids(db: Session, tag_ids: list[str]) -> None:
    for tag_id in set(tag_ids):
        remaining = db.scalar(
            select(func.count()).select_from(UserTagLink).where(UserTagLink.tag_id == tag_id)
        )
        if remaining:
            continue
        row = db.get(UserTag, tag_id)
        if row is not None:
            db.delete(row)


def delete_all_user_tags(db: Session, user_id: str) -> None:
    db.execute(delete(UserTagLink).where(UserTagLink.user_id == user_id))
    db.execute(delete(UserTag).where(UserTag.user_id == user_id))


def _prune_unused_tags(db: Session, user_id: str) -> None:
    db.execute(
        delete(UserTag).where(
            UserTag.user_id == user_id,
            ~UserTag.id.in_(select(UserTagLink.tag_id).where(UserTagLink.user_id == user_id)),
        )
    )
