"""Instance admin org list helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.deps import AuthContext, get_instance_settings
from app.models import HiddenItem, Membership, Organization, User
from app.presenters import org_public, user_public
def list_orgs_payload(
    ctx: AuthContext,
    db: Session,
    *,
    include_hidden: bool,
) -> dict:
    settings = get_instance_settings(db)
    rows = list(
        db.scalars(
            select(Organization).options(joinedload(Organization.tariff)).order_by(Organization.created_at)
        ).all()
    )
    org_ids = [org.id for org in rows]
    hidden_org_ids: set[str] = set()
    if org_ids:
        hidden_org_ids = set(
            db.scalars(
                select(HiddenItem.object_id).where(
                    HiddenItem.user_id == ctx.user.id,
                    HiddenItem.object_type == "org",
                    HiddenItem.object_id.in_(org_ids),
                )
            ).all()
        )

    memberships_by_org: dict[str, list[Membership]] = {oid: [] for oid in org_ids}
    if org_ids:
        for membership in db.scalars(select(Membership).where(Membership.org_id.in_(org_ids))).all():
            memberships_by_org[membership.org_id].append(membership)

    user_ids = {m.user_id for memberships in memberships_by_org.values() for m in memberships}
    users = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    )

    items = []
    for org in rows:
        hidden = org.id in hidden_org_ids
        if not include_hidden and hidden:
            continue
        payload = org_public(org)
        payload["hidden"] = hidden
        payload["members"] = []
        for membership in memberships_by_org.get(org.id, []):
            user = users.get(membership.user_id)
            if user:
                payload["members"].append(user_public(user, membership.role, instance_settings=settings))
        items.append(payload)
    return {"items": items, "hidden_count": len(hidden_org_ids)}
