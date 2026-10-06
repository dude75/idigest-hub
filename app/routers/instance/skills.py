from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import AuthContext, require_auth
from app.errors import ErrorCode
from app.models import new_id
from app.routers.instance._body import BaseSkillBody
from app.routers.instance._router import router
from app.schemas.common import OkStatusResponse
from app.schemas.skills_api import SkillListResponse, SkillPublicResponse
from app.services.instance_helpers import require_instance_admin
from app.timeutil import utcnow

@router.get("/skills/base", response_model=SkillListResponse)
def list_base_skills(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> SkillListResponse:
    from app.models import Skill
    from app.presenters import skill_public

    require_instance_admin(ctx)
    rows = db.scalars(select(Skill).where(Skill.scope == "base").order_by(Skill.name)).all()
    return SkillListResponse(items=[SkillPublicResponse.model_validate(skill_public(row)) for row in rows])


@router.post("/skills/base", response_model=SkillPublicResponse)
def create_base_skill(
    body: BaseSkillBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> SkillPublicResponse:
    from app.models import Skill
    from app.presenters import skill_public

    require_instance_admin(ctx)
    now = utcnow()
    skill = Skill(
        id=new_id(),
        scope="base",
        name=body.name.strip(),
        body=body.body,
        created_at=now,
        updated_at=now,
    )
    db.add(skill)
    db.flush()
    return SkillPublicResponse.model_validate(skill_public(skill))


@router.patch("/skills/base/{skill_id}", response_model=SkillPublicResponse)
def patch_base_skill(
    skill_id: str,
    body: BaseSkillBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> SkillPublicResponse:
    from app.models import Skill
    from app.presenters import skill_public

    require_instance_admin(ctx)
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "base":
        ctx.raise_error(ErrorCode.not_found)
    skill.name = body.name.strip()
    skill.body = body.body
    skill.updated_at = utcnow()
    return SkillPublicResponse.model_validate(skill_public(skill))


@router.delete("/skills/base/{skill_id}", response_model=OkStatusResponse)
def delete_base_skill(
    skill_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
    from app.models import Skill

    require_instance_admin(ctx)
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "base":
        ctx.raise_error(ErrorCode.not_found)
    db.delete(skill)
    return OkStatusResponse()
