"""Unauthenticated public content endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.crypto import decrypt_str
from app.db import get_session
from app.errors import ApiError, ErrorCode
from app.i18n import negotiate_locale
from app.rate_limit import client_ip, enforce_public_link_view, enforce_public_pin_unlock, get_rate_limits
from app.services.audit import write_public_audit
from app.deps import get_instance_settings
from app.services.public_links import (
    resolve_link,
    set_unlock_cookie,
    summary_guest_payload,
    unlock_cookie_valid,
    verify_link_pin,
)
from app.services.user_agreement import (
    LEGAL_DOCUMENT_KEYS,
    LEGAL_DOCUMENT_SPECS,
    document_active,
    document_published,
    document_text,
    public_landing_footer_text,
    public_legal_documents,
)

router = APIRouter()


class PublicUnlockBody(BaseModel):
    pin: str = Field(min_length=1, max_length=32)


def _locale(request: Request) -> str:
    return negotiate_locale(request.headers.get("accept-language"))


def _pin_required_payload() -> dict:
    return {"pin_required": True}


@router.get("/public/legal-documents")
def list_public_legal_documents(
    request: Request,
    db: Session = Depends(get_session, scope="function"),
) -> dict:
    locale = _locale(request)
    settings = get_instance_settings(db)
    return {
        "items": public_legal_documents(settings, locale),
        "footer_text": public_landing_footer_text(settings, locale),
    }


@router.get("/public/legal-documents/{key}")
def get_public_legal_document(
    key: str,
    request: Request,
    db: Session = Depends(get_session, scope="function"),
) -> dict:
    if key not in LEGAL_DOCUMENT_KEYS:
        raise ApiError(ErrorCode.not_found)
    locale = _locale(request)
    settings = get_instance_settings(db)
    if not document_active(settings, key) or not document_published(settings, key):
        raise ApiError(ErrorCode.not_found)
    spec = LEGAL_DOCUMENT_SPECS[key]
    return {
        "key": key,
        "version": getattr(settings, spec["version"]),
        "text": document_text(settings, key, locale),
    }


@router.get("/public/summary/{token}")
def get_public_summary(
    token: str,
    request: Request,
    db: Session = Depends(get_session, scope="function"),
) -> dict:
    locale = _locale(request)
    enforce_public_link_view(client_ip(request), get_rate_limits(db), locale)
    resolved = resolve_link(db, token)
    if resolved is None:
        raise ApiError(ErrorCode.not_found)
    link, summary, org = resolved
    if link.pin_hash is not None and not unlock_cookie_valid(request, link):
        return _pin_required_payload()
    body_text = decrypt_str(summary.body_encrypted, db)
    write_public_audit(db, "summary.public_link.view", org_id=org.id, payload={"summary_id": summary.id, "link_id": link.id})
    return {"pin_required": False, **summary_guest_payload(summary, body_text)}


@router.post("/public/summary/{token}/unlock")
def unlock_public_summary(
    token: str,
    body: PublicUnlockBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
) -> dict:
    locale = _locale(request)
    enforce_public_pin_unlock(client_ip(request), get_rate_limits(db), locale)
    resolved = resolve_link(db, token)
    if resolved is None:
        raise ApiError(ErrorCode.not_found)
    link, summary, org = resolved
    if link.pin_hash is None:
        body_text = decrypt_str(summary.body_encrypted, db)
        write_public_audit(db, "summary.public_link.view", org_id=org.id, payload={"summary_id": summary.id, "link_id": link.id})
        return {"pin_required": False, **summary_guest_payload(summary, body_text)}
    if not verify_link_pin(link, body.pin):
        raise ApiError(ErrorCode.invalid_pin)
    set_unlock_cookie(response, link)
    body_text = decrypt_str(summary.body_encrypted, db)
    write_public_audit(db, "summary.public_link.view", org_id=org.id, payload={"summary_id": summary.id, "link_id": link.id})
    return {"pin_required": False, **summary_guest_payload(summary, body_text)}
