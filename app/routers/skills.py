"""Каталог скилов: base / org / self / shared, copy (ТЗ §9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import AuthContext, require_auth
from app.errors import ErrorCode
from app.models import Share, Skill, new_id
from app.presenters import skill_public
from app.services.access import is_shared_with
from app.timeutil import utcnow

router = APIRouter()


class SkillBody(BaseModel):
    name: str
    body: str


def _visible_skills(db: Session, ctx: AuthContext, scope: str | None) -> list[tuple[Skill, dict]]:
    org, _ = ctx.require_org()
    items: list[tuple[Skill, dict]] = []
    base = db.scalars(select(Skill).where(Skill.scope == "base")).all()
    org_skills = db.scalars(select(Skill).where(Skill.scope == "org", Skill.org_id == org.id)).all()
    mine = db.scalars(
        select(Skill).where(Skill.scope == "self", Skill.owner_user_id == ctx.user.id)
    ).all()
    shared_ids = [
        row.object_id
        for row in db.scalars(
            select(Share).where(Share.to_user_id == ctx.user.id, Share.object_type == "skill")
        ).all()
    ]
    shared = db.scalars(select(Skill).where(Skill.id.in_(shared_ids))).all() if shared_ids else []

    def add(skill: Skill, extra: dict, bucket: str) -> None:
        if scope and bucket != scope:
            return
        extra = dict(extra)
        extra["catalog"] = bucket
        extra["readonly"] = bucket in {"shared", "base"} or (
            bucket == "org" and not ctx.is_org_admin
        )
        if bucket == "base":
            extra["readonly"] = not ctx.is_instance_admin
        items.append((skill, extra))

    for skill in base:
        add(skill, {}, "base")
    for skill in org_skills:
        add(skill, {}, "org")
    for skill in mine:
        add(skill, {}, "self")
    for skill in shared:
        add(skill, {"share_kind": "incoming"}, "shared")
    return items


@router.get("/skills")
def catalog(
    scope: str | None = None,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    items = _visible_skills(db, ctx, scope)
    return {"items": [skill_public(skill, extra) for skill, extra in items]}


@router.post("/skills/self")
def create_self(
    body: SkillBody, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org()
    now = utcnow()
    skill = Skill(
        id=new_id(),
        scope="self",
        org_id=org.id,
        owner_user_id=ctx.user.id,
        name=body.name.strip(),
        body=body.body,
        created_at=now,
        updated_at=now,
    )
    db.add(skill)
    db.flush()
    return skill_public(skill)


@router.patch("/skills/self/{skill_id}")
def patch_self(
    skill_id: str,
    body: SkillBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "self" or skill.owner_user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.not_found)
    skill.name = body.name.strip()
    skill.body = body.body
    skill.updated_at = utcnow()
    return skill_public(skill)


@router.delete("/skills/self/{skill_id}")
def delete_self(
    skill_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "self" or skill.owner_user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.not_found)
    db.delete(skill)
    return {"status": "ok"}


@router.post("/org/skills")
def create_org_skill(
    body: SkillBody, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org_admin()
    now = utcnow()
    skill = Skill(
        id=new_id(),
        scope="org",
        org_id=org.id,
        name=body.name.strip(),
        body=body.body,
        created_at=now,
        updated_at=now,
    )
    db.add(skill)
    db.flush()
    return skill_public(skill)


@router.patch("/org/skills/{skill_id}")
def patch_org_skill(
    skill_id: str,
    body: SkillBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org_admin()
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "org" or skill.org_id != org.id:
        ctx.raise_error(ErrorCode.not_found)
    skill.name = body.name.strip()
    skill.body = body.body
    skill.updated_at = utcnow()
    return skill_public(skill)


@router.delete("/org/skills/{skill_id}")
def delete_org_skill(
    skill_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org_admin()
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "org" or skill.org_id != org.id:
        ctx.raise_error(ErrorCode.not_found)
    db.delete(skill)
    return {"status": "ok"}


@router.post("/skills/{skill_id}/copy")
def copy_skill(
    skill_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org()
    skill = db.get(Skill, skill_id)
    if skill is None:
        ctx.raise_error(ErrorCode.not_found)
    allowed = False
    if skill.scope == "base":
        allowed = True
    elif skill.scope == "org" and skill.org_id == org.id:
        allowed = True
    elif skill.scope == "self" and (
        skill.owner_user_id == ctx.user.id or is_shared_with(db, "skill", skill.id, ctx.user.id)
    ):
        allowed = True
    if not allowed:
        ctx.raise_error(ErrorCode.forbidden)
    now = utcnow()
    copy = Skill(
        id=new_id(),
        scope="self",
        org_id=org.id,
        owner_user_id=ctx.user.id,
        name=skill.name,
        body=skill.body,
        created_at=now,
        updated_at=now,
    )
    db.add(copy)
    db.flush()
    return skill_public(copy)
