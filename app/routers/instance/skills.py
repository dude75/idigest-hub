from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crypto import encrypt_str
from app.db import get_session
from app.deps import (
    AuthContext,
    get_instance_settings,
    invalidate_session_ttl_cache,
    load_org_bundle,
    normalize_session_ttl_hours,
    require_auth,
)
from app.errors import ApiError, ErrorCode
from app.models import HiddenItem, Membership, Organization, Task, Tariff, User, WorkerNode, new_id
from app.money import parse_money
from app.presenters import org_public, tariff_public, user_public, worker_public
from app.rate_limit import invalidate_rate_limit_cache, rate_limits_public
from app.services.auth_helpers import revoke_user_auth, seed_default_tariff
from app.routers.instance._body import (
    AgreementPreviewBody,
    BaseSkillBody,
    CreateOrgBody,
    ImpersonateBody,
    OrgDeleteBody,
    OrgTariffBody,
    OrgUserRoleBody,
    SettingsPatch,
    SmtpTestBody,
    SmtpTestSendBody,
    TariffBody,
    TariffCloneBody,
    TariffDeleteBody,
    WalletBody,
    WorkerBody,
    WorkerDeleteBody,
    WorkerProbeBody,
    WorkerRemediation,
)
from app.routers.instance._router import router
from app.security import hash_password, random_password
from app.services.access import guard_last_org_admin, is_hidden
from app.services.audit import export_audit_csv, list_audit, write_audit
from app.services.billing import signup_balance
from app.services.export import attachment_response, safe_filename
from app.services.instance_helpers import (
    apply_capture_worker_models,
    apply_transcribe_worker_models,
    org_count_for_tariff,
    raise_worker_connect_error,
    require_instance_admin,
    resolve_worker_token,
    workers_list_payload,
)
from app.services.instance_orgs import list_orgs_payload
from app.services.mfa import disable_totp, hub_local_auth_applies, totp_configured
from app.services.stats import org_ledger, parse_org_stats_range, usage_stats
from app.timeutil import utcnow

@router.get("/skills/base")
def list_base_skills(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> dict:
    from app.models import Skill
    from app.presenters import skill_public

    require_instance_admin(ctx)
    rows = db.scalars(select(Skill).where(Skill.scope == "base").order_by(Skill.name)).all()
    return {"items": [skill_public(row) for row in rows]}


@router.post("/skills/base")
def create_base_skill(
    body: BaseSkillBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
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
    return skill_public(skill)


@router.patch("/skills/base/{skill_id}")
def patch_base_skill(
    skill_id: str,
    body: BaseSkillBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    from app.models import Skill
    from app.presenters import skill_public

    require_instance_admin(ctx)
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "base":
        ctx.raise_error(ErrorCode.not_found)
    skill.name = body.name.strip()
    skill.body = body.body
    skill.updated_at = utcnow()
    return skill_public(skill)


@router.delete("/skills/base/{skill_id}")
def delete_base_skill(
    skill_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.models import Skill

    require_instance_admin(ctx)
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "base":
        ctx.raise_error(ErrorCode.not_found)
    db.delete(skill)
    return {"status": "ok"}
