from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.constants import COOKIE_NAME
from app.cookies import clear_auth_cookies, issue_auth_cookies, oauth_embedded_session_samesite
from app.db import get_session
from app.deps import AuthContext, abort, get_instance_settings, locale_from_request, optional_auth, require_auth, session_ttl_sec_from_db
from app.errors import ErrorCode
from app.models import (
    ApiToken,
    InstanceSettings,
    Membership,
    Organization,
    PasswordResetToken,
    Session as AuthSession,
    Tariff,
    User,
    new_id,
)
from app.presenters import token_public
from app.routers.auth._body import TokenCreateBody
from app.routers.auth._router import router
from app.security import hash_password, hash_secret, new_api_token, new_reset_token, verify_password
from app.services.audit import write_audit
from app.services.auth_helpers import create_session, me_payload, me_with_csrf, public_base_url, revoke_user_auth, seed_default_tariff, sso_login_redirect
from app.timeutil import utcnow

from app.schemas.auth_api import ApiTokenCreateResponse, ApiTokenListResponse, ApiTokenPublic, OkStatusResponse
from app.services.mfa import mfa_enrollment_required, totp_enabled, verify_user_totp

@router.post("/auth/tokens", response_model=ApiTokenCreateResponse)
def create_token(
    body: TokenCreateBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> ApiTokenCreateResponse:
    if ctx.via_api_token or ctx.impersonating:
        ctx.raise_error(ErrorCode.forbidden)
    if ctx.user.must_change_password:
        ctx.raise_error(ErrorCode.must_change_password)
    if mfa_enrollment_required(user=ctx.user, org=ctx.org, membership=ctx.membership):
        ctx.raise_error(ErrorCode.mfa_enrollment_required)
    from app.services.user_agreement import user_agreement_required

    if user_agreement_required(
        user=ctx.user,
        org=ctx.org,
        membership=ctx.membership,
        settings=get_instance_settings(db),
    ):
        ctx.raise_error(ErrorCode.user_agreement_required)
    from app.services.billing import org_api_enabled

    if not org_api_enabled(ctx.org):
        ctx.raise_error(ErrorCode.api_disabled)
    if totp_enabled(ctx.user):
        if not body.totp_code:
            ctx.raise_error(ErrorCode.mfa_step_up_required)
        if not verify_user_totp(ctx.user, body.totp_code, db):
            ctx.raise_error(ErrorCode.invalid_totp)
    raw = new_api_token()
    now = utcnow()
    row = ApiToken(
        id=new_id(),
        user_id=ctx.user.id,
        name=body.name.strip(),
        token_hash=hash_secret(raw),
        prefix=raw[:10],
        created_at=now,
    )
    db.add(row)
    db.flush()
    payload = token_public(row)
    payload["token"] = raw
    return ApiTokenCreateResponse.model_validate(payload)


@router.get("/auth/tokens", response_model=ApiTokenListResponse)
def list_tokens(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> ApiTokenListResponse:
    rows = db.scalars(select(ApiToken).where(ApiToken.user_id == ctx.user.id).order_by(ApiToken.created_at.desc()))
    from app.services.billing import org_api_enabled

    blocked = not org_api_enabled(ctx.org)
    return ApiTokenListResponse(
        items=[ApiTokenPublic.model_validate(token_public(row, blocked_by_tariff=blocked)) for row in rows]
    )


@router.delete("/auth/tokens/{token_id}", response_model=OkStatusResponse)
def revoke_token(
    token_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> OkStatusResponse:
    row = db.get(ApiToken, token_id)
    if row is None or row.user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.not_found)
    row.revoked_at = utcnow()
    return OkStatusResponse()
