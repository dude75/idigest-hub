"""Public read-only links for summaries."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import (
    PUBLIC_LINK_PIN_MAX_LEN,
    PUBLIC_LINK_PIN_MIN_LEN,
    PUBLIC_LINK_UNLOCK_COOKIE,
    PUBLIC_LINK_UNLOCK_TTL_SEC,
)
from app.crypto import decrypt_str
from app.deps import get_instance_settings
from app.errors import ApiError, ErrorCode
from app.models import Organization, Summary, SummaryPublicLink, User, new_id
from app.presenters import summary_display_title
from app.security import compare_digest, hash_password, hash_secret, new_reset_token, verify_password
from app.timeutil import as_utc, isoformat_utc, utcnow


def instance_public_base_url(db: Session) -> str | None:
    settings = get_instance_settings(db)
    value = (settings.public_base_url or "").strip().rstrip("/")
    return value or None


def org_allows_public_links(org: Organization, db: Session) -> bool:
    if not org.allow_public_links:
        return False
    return instance_public_base_url(db) is not None


def link_is_active(link: SummaryPublicLink, org: Organization, db: Session, *, now: datetime | None = None) -> bool:
    moment = now or utcnow()
    if link.revoked_at is not None:
        return False
    if link.expires_at is not None and as_utc(link.expires_at) <= moment:
        return False
    if not org.allow_public_links:
        return False
    return instance_public_base_url(db) is not None


def public_summary_url(db: Session, raw_token: str) -> str | None:
    base = instance_public_base_url(db)
    if not base:
        return None
    return f"{base}/public/summary/{raw_token}"


def _validate_pin(pin: str | None) -> str | None:
    if pin is None or pin == "":
        return None
    cleaned = pin.strip()
    if not cleaned.isdigit():
        raise ValueError("pin_not_digits")
    if len(cleaned) < PUBLIC_LINK_PIN_MIN_LEN or len(cleaned) > PUBLIC_LINK_PIN_MAX_LEN:
        raise ValueError("pin_length")
    return cleaned


def _expires_at(expires_in_days: int | None) -> datetime | None:
    if expires_in_days is None:
        return None
    if expires_in_days <= 0:
        raise ValueError("expires_in_days")
    return utcnow() + timedelta(days=expires_in_days)


def get_link_for_summary(db: Session, summary_id: str) -> SummaryPublicLink | None:
    return db.scalar(select(SummaryPublicLink).where(SummaryPublicLink.summary_id == summary_id))


def resolve_link(db: Session, raw_token: str) -> tuple[SummaryPublicLink, Summary, Organization] | None:
    row = db.scalar(select(SummaryPublicLink).where(SummaryPublicLink.token_hash == hash_secret(raw_token)))
    if row is None:
        return None
    summary = db.get(Summary, row.summary_id)
    org = db.get(Organization, row.org_id)
    if summary is None or org is None:
        return None
    if not link_is_active(row, org, db):
        return None
    return row, summary, org


def link_public_payload(link: SummaryPublicLink, db: Session) -> dict:
    raw = decrypt_str(link.token_encrypted, db)
    url = public_summary_url(db, raw)
    return {
        "id": link.id,
        "summary_id": link.summary_id,
        "url": url,
        "expires_at": isoformat_utc(link.expires_at),
        "pin_required": link.pin_hash is not None,
        "created_at": isoformat_utc(link.created_at),
        "revoked": link.revoked_at is not None,
    }


def create_or_update_link(
    db: Session,
    *,
    summary: Summary,
    org: Organization,
    user: User,
    expires_in_days: int | None,
    pin: str | None,
) -> tuple[SummaryPublicLink, str]:
    if not org_allows_public_links(org, db):
        if not instance_public_base_url(db):
            raise ApiError(ErrorCode.public_base_url_missing)
        raise ApiError(ErrorCode.public_links_disabled)

    try:
        pin_clean = _validate_pin(pin)
        expires = _expires_at(expires_in_days)
    except ValueError:
        raise ApiError(ErrorCode.validation_error)

    existing = get_link_for_summary(db, summary.id)
    if existing is not None:
        if existing.revoked_at is not None:
            db.delete(existing)
            db.flush()
        else:
            existing.expires_at = expires
            existing.pin_hash = hash_password(pin_clean) if pin_clean else None
            raw = decrypt_str(existing.token_encrypted, db)
            return existing, raw

    from app.crypto import encrypt_str

    raw = new_reset_token()
    row = SummaryPublicLink(
        id=new_id(),
        summary_id=summary.id,
        org_id=summary.org_id,
        token_hash=hash_secret(raw),
        token_encrypted=encrypt_str(raw, db),
        created_by_user_id=user.id,
        expires_at=expires,
        revoked_at=None,
        pin_hash=hash_password(pin_clean) if pin_clean else None,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return row, raw


def revoke_link(db: Session, link: SummaryPublicLink) -> None:
    db.delete(link)


def verify_link_pin(link: SummaryPublicLink, pin: str) -> bool:
    if link.pin_hash is None:
        return True
    return verify_password(pin.strip(), link.pin_hash)


def summary_guest_payload(summary: Summary, body_text: str) -> dict:
    return {
        "title": summary.title,
        "display_title": summary_display_title(summary),
        "body": body_text,
    }


def unlock_cookie_value(link_id: str, *, expires_at: datetime) -> str:
    ts = int(expires_at.timestamp())
    sig = hash_secret(f"plu:{link_id}:{ts}")
    return f"{link_id}.{ts}.{sig}"


def parse_unlock_cookie(value: str) -> tuple[str, int] | None:
    parts = value.split(".")
    if len(parts) != 3:
        return None
    link_id, ts_raw, sig = parts
    if not link_id or not ts_raw.isdigit():
        return None
    ts = int(ts_raw)
    expected = hash_secret(f"plu:{link_id}:{ts}")
    if not compare_digest(sig, expected):
        return None
    return link_id, ts


def unlock_cookie_valid(request: Request, link: SummaryPublicLink) -> bool:
    raw = request.cookies.get(PUBLIC_LINK_UNLOCK_COOKIE)
    if not raw:
        return False
    parsed = parse_unlock_cookie(raw)
    if parsed is None:
        return False
    link_id, ts = parsed
    if link_id != link.id:
        return False
    if ts <= int(utcnow().timestamp()):
        return False
    return True


def set_unlock_cookie(response: Response, link: SummaryPublicLink) -> None:
    from app.config import get_settings

    expires = utcnow() + timedelta(seconds=PUBLIC_LINK_UNLOCK_TTL_SEC)
    settings = get_settings()
    response.set_cookie(
        key=PUBLIC_LINK_UNLOCK_COOKIE,
        value=unlock_cookie_value(link.id, expires_at=expires),
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=PUBLIC_LINK_UNLOCK_TTL_SEC,
        path="/",
    )


def link_org_list_item(
    link: SummaryPublicLink, summary: Summary, owner: User, org: Organization, db: Session
) -> dict:
    from app.presenters import summary_display_title

    payload = link_public_payload(link, db)
    payload["summary_title"] = summary_display_title(summary)
    payload["owner_email"] = owner.email
    payload["active"] = link_is_active(link, org, db)
    return payload


def list_org_public_links(db: Session, org_id: str) -> list[tuple[SummaryPublicLink, Summary, User]]:
    rows = db.scalars(
        select(SummaryPublicLink)
        .where(SummaryPublicLink.org_id == org_id)
        .order_by(SummaryPublicLink.created_at.desc())
    ).all()
    out: list[tuple[SummaryPublicLink, Summary, User]] = []
    for link in rows:
        summary = db.get(Summary, link.summary_id)
        owner = db.get(User, summary.owner_user_id) if summary else None
        if summary is None or owner is None:
            continue
        out.append((link, summary, owner))
    return out
