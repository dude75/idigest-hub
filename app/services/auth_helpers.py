"""Shared auth/session helpers (used by auth router and other modules)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_TARIFF_NAME, MAX_UPLOAD_BYTES_CAP
from app.cookies import bind_csrf_token
from app.deps import AuthContext, get_instance_settings, session_ttl_sec_from_db
from app.errors import ErrorCode
from app.models import ApiToken, Membership, Organization, Session as AuthSession, Tariff, UsageEvent, User, new_id
from app.presenters import org_public, user_public
from app.security import hash_secret, new_session_token
from app.services.mfa import mfa_enrollment_required, org_mfa_required, totp_enabled
from app.timeutil import as_utc, utcnow


def seed_default_tariff(db: Session) -> Tariff:
    existing = db.scalar(select(Tariff).limit(1))
    if existing is not None:
        return existing
    now = utcnow()
    tariff = Tariff(
        id=new_id(),
        name=DEFAULT_TARIFF_NAME,
        unlimited=True,
        available_on_signup=True,
        archived_at=None,
        price_per_audio_sec=Decimal("0"),
        price_per_summarize_job=Decimal("0"),
        price_per_1k_summary_chars=Decimal("0"),
        audio_retention_days=0,
        api_enabled=True,
        signup_credit=Decimal("0.00"),
        max_upload_bytes=MAX_UPLOAD_BYTES_CAP,
        created_at=now,
        updated_at=now,
    )
    db.add(tariff)
    db.flush()
    return tariff


def create_session(db: Session, user_id: str) -> str:
    raw = new_session_token()
    now = utcnow()
    ttl_sec = session_ttl_sec_from_db(db)
    db.add(
        AuthSession(
            id=new_id(),
            user_id=user_id,
            token_hash=hash_secret(raw),
            impersonate_user_id=None,
            expires_at=now + timedelta(seconds=ttl_sec),
            created_at=now,
            last_seen_at=now,
        )
    )
    return raw


def invalidate_user_sessions(db: Session, user_id: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


def revoke_user_tokens(db: Session, user_id: str) -> None:
    now = utcnow()
    tokens = db.scalars(select(ApiToken).where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None)))
    for token in tokens:
        token.revoked_at = now


def revoke_user_auth(db: Session, user_id: str) -> None:
    invalidate_user_sessions(db, user_id)
    revoke_user_tokens(db, user_id)


def public_base_url(db: Session) -> str | None:
    settings = get_instance_settings(db)
    value = (settings.public_base_url or "").strip()
    return value or None


def sso_login_redirect(public_base: str, org_id: str, code: ErrorCode) -> RedirectResponse:
    query = urlencode({"error": code.value})
    return RedirectResponse(f"{public_base.rstrip('/')}/sso/{org_id}?{query}", status_code=302)


def _summarize_me_payload(user: User, settings, db: Session) -> dict:
    from app.services.summarize_models import aggregate_instance_summarize_models, resolve_summarize_models

    available = aggregate_instance_summarize_models(db)
    return {
        "summarize_prefs": resolve_summarize_models(user, settings, available=available["summarize_models"]),
        "summarize_models": available,
    }


def me_payload(ctx: AuthContext, db: Session) -> dict:
    role = ctx.membership.role if ctx.membership else ("instance_admin" if ctx.user.is_instance_admin else None)
    usage = None
    if ctx.org is not None:
        total = db.scalar(
            select(func.coalesce(func.sum(UsageEvent.amount), 0)).where(UsageEvent.org_id == ctx.org.id)
        )
        usage = {"total_amount": str(total)}
    enrollment_required = mfa_enrollment_required(
        user=ctx.user,
        org=ctx.org,
        membership=ctx.membership,
    )
    from app.datetime_format import resolve_date_time_prefs
    from app.services.transcribe_models import aggregate_instance_models, resolve_transcribe_models
    from app.services.user_agreement import (
        agreement_active,
        agreement_text,
        member_legal_documents,
        user_agreement_required,
    )

    settings = get_instance_settings(db)
    from app.services.capture_meeting import resolve_capture_prefs

    capture_prefs = resolve_capture_prefs(ctx.user, ctx.org, settings)
    agreement_pending = user_agreement_required(
        user=ctx.user,
        org=ctx.org,
        membership=ctx.membership,
        settings=settings,
    )
    agreement_payload = None
    legal_documents = None
    if ctx.membership is not None and ctx.org is not None:
        legal_documents = member_legal_documents(ctx.user, settings, ctx.locale)
        if agreement_active(settings):
            agreement_payload = {
                "version": settings.user_agreement_version,
                "text": agreement_text(settings, ctx.locale),
            }
    return {
        "user": user_public(ctx.user, role),
        "org": org_public(ctx.org, usage=usage, public_base_url=public_base_url(db)) if ctx.org else None,
        "impersonating": ctx.impersonating,
        "actor": user_public(ctx.actor) if ctx.impersonating else None,
        "date_time_prefs": resolve_date_time_prefs(ctx.user, settings),
        "transcribe_prefs": resolve_transcribe_models(ctx.user, settings),
        "transcribe_models": aggregate_instance_models(db),
        "capture_prefs": capture_prefs,
        **_summarize_me_payload(ctx.user, settings, db),
        "must_change_password": ctx.user.must_change_password
        or (
            ctx.org is not None
            and ctx.org.password_ttl_days > 0
            and ctx.user.password_changed_at is not None
            and utcnow()
            >= as_utc(ctx.user.password_changed_at) + timedelta(days=ctx.org.password_ttl_days)
        ),
        "mfa_enabled": totp_enabled(ctx.user),
        "mfa_required": org_mfa_required(user=ctx.user, org=ctx.org, membership=ctx.membership),
        "mfa_enrollment_required": enrollment_required,
        "user_agreement_required": agreement_pending,
        "user_agreement": agreement_payload,
        "user_agreement_version": settings.user_agreement_version if agreement_active(settings) else None,
        "legal_documents": legal_documents,
    }


def me_with_csrf(request: Request, response: Response, ctx: AuthContext, db: Session) -> dict:
    token = bind_csrf_token(request, response, max_age=session_ttl_sec_from_db(db))
    payload = me_payload(ctx, db)
    payload["csrf_token"] = token
    return payload
