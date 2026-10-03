"""Library list visibility (SQL) and batched share/hidden badges for list endpoints."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.deps import AuthContext
from app.models import HiddenItem, Share, User, UserTagLink
from app.services.user_tags import resolve_user_tag


LIBRARY_LIST_MAX_LIMIT = 500


def library_visibility_filters(
    ctx: AuthContext,
    db: Session,
    model: type,
    object_type: str,
    *,
    include_hidden: bool,
    tag: str | None,
    owner_user_id: str | None = None,
) -> list[Any] | None:
    """WHERE clauses for visible library rows. None => empty list (unknown tag)."""
    org, membership = ctx.require_org()
    filters: list[Any] = [model.org_id == org.id]
    if membership.role != "org_admin":
        incoming_share = exists(
            select(1).where(
                Share.object_type == object_type,
                Share.object_id == model.id,
                Share.to_user_id == ctx.user.id,
            )
        )
        filters.append(or_(model.owner_user_id == ctx.user.id, incoming_share))
    if owner_user_id:
        filters.append(model.owner_user_id == owner_user_id)
    if not include_hidden:
        hidden_row = exists(
            select(1).where(
                HiddenItem.user_id == ctx.user.id,
                HiddenItem.object_type == object_type,
                HiddenItem.object_id == model.id,
            )
        )
        filters.append(~hidden_row)
    if tag:
        row_tag = resolve_user_tag(db, ctx.user.id, tag)
        if row_tag is None:
            return None
        filters.append(
            model.id.in_(
                select(UserTagLink.object_id).where(
                    UserTagLink.user_id == ctx.user.id,
                    UserTagLink.object_type == object_type,
                    UserTagLink.tag_id == row_tag.id,
                )
            )
        )
    return filters


def list_library_rows(
    ctx: AuthContext,
    db: Session,
    model: type,
    object_type: str,
    include_hidden: bool,
    tag: str | None = None,
    *,
    owner_user_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Any]:
    filters = library_visibility_filters(
        ctx,
        db,
        model,
        object_type,
        include_hidden=include_hidden,
        tag=tag,
        owner_user_id=owner_user_id,
    )
    if filters is None:
        return []
    query = select(model).where(*filters).order_by(model.created_at.desc())
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return list(db.scalars(query).all())


def count_library_rows(
    ctx: AuthContext,
    db: Session,
    model: type,
    object_type: str,
    include_hidden: bool,
    tag: str | None = None,
    *,
    owner_user_id: str | None = None,
) -> int:
    filters = library_visibility_filters(
        ctx,
        db,
        model,
        object_type,
        include_hidden=include_hidden,
        tag=tag,
        owner_user_id=owner_user_id,
    )
    if filters is None:
        return 0
    return int(db.scalar(select(func.count()).select_from(model).where(*filters)) or 0)


def count_hidden_library_rows(
    ctx: AuthContext,
    db: Session,
    model: type,
    object_type: str,
) -> int:
    """Rows the user may access that are marked hidden (matches legacy hidden_count)."""
    filters = library_visibility_filters(
        ctx, db, model, object_type, include_hidden=True, tag=None
    )
    if filters is None:
        return 0
    hidden_row = exists(
        select(1).where(
            HiddenItem.user_id == ctx.user.id,
            HiddenItem.object_type == object_type,
            HiddenItem.object_id == model.id,
        )
    )
    return int(
        db.scalar(select(func.count()).select_from(model).where(*filters, hidden_row)) or 0
    )


def _share_items_from_map(rows: list[Share], emails: dict[str, str]) -> list[dict]:
    return [
        {
            "id": row.id,
            "to_user_id": row.to_user_id,
            "email": emails.get(row.to_user_id, row.to_user_id),
        }
        for row in rows
    ]


def batch_share_badges(
    db: Session,
    ctx: AuthContext,
    object_type: str,
    rows: list[Any],
    *,
    user_tags_by_id: dict[str, list[dict]] | None = None,
) -> dict[str, dict]:
    """One round of queries for list endpoints (replaces per-row _share_badge)."""
    if not rows:
        return {}
    user_tags_by_id = user_tags_by_id or {}
    object_ids = [row.id for row in rows]
    user_id = ctx.user.id

    hidden_ids = set(
        db.scalars(
            select(HiddenItem.object_id).where(
                HiddenItem.user_id == user_id,
                HiddenItem.object_type == object_type,
                HiddenItem.object_id.in_(object_ids),
            )
        ).all()
    )

    incoming_by_object: dict[str, Share] = {}
    for share in db.scalars(
        select(Share).where(
            Share.object_type == object_type,
            Share.object_id.in_(object_ids),
            Share.to_user_id == user_id,
        )
    ).all():
        incoming_by_object[share.object_id] = share

    owned_ids = [row.id for row in rows if row.owner_user_id == user_id]
    outgoing_by_object: dict[str, list[Share]] = defaultdict(list)
    if owned_ids:
        for share in db.scalars(
            select(Share).where(
                Share.object_type == object_type,
                Share.object_id.in_(owned_ids),
            )
        ).all():
            outgoing_by_object[share.object_id].append(share)

    email_ids: set[str] = {row.owner_user_id for row in rows}
    for share in incoming_by_object.values():
        email_ids.add(share.from_user_id)
    for shares in outgoing_by_object.values():
        for share in shares:
            email_ids.add(share.to_user_id)

    emails = (
        {
            u.id: u.email
            for u in db.scalars(select(User).where(User.id.in_(email_ids))).all()
        }
        if email_ids
        else {}
    )

    result: dict[str, dict] = {}
    for row in rows:
        extra: dict[str, Any] = {
            "hidden": row.id in hidden_ids,
            "owner_email": emails.get(row.owner_user_id),
            "user_tags": user_tags_by_id.get(row.id, []),
        }
        if row.owner_user_id == user_id:
            outgoing = outgoing_by_object.get(row.id, [])
            extra["shared_with"] = [s.to_user_id for s in outgoing]
            extra["shares"] = _share_items_from_map(outgoing, emails)
            extra["share_kind"] = "outgoing" if outgoing else None
        else:
            inc = incoming_by_object.get(row.id)
            if inc:
                extra["share_kind"] = "incoming"
                extra["shared_by"] = emails.get(inc.from_user_id, inc.from_user_id)
                extra["share_id"] = inc.id
        result[row.id] = extra
    return result
