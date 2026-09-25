"""OIDC SSO (Keycloak-compatible) per organization."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx2
import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import decrypt_str, encrypt_str, try_decrypt_str
from app.models import Membership, Organization, User, new_id
from app.security import hash_password, random_password

log = logging.getLogger("app")

STATE_TTL_SEC = 600
AUTH_PROVIDER_OIDC = "oidc"
_PKCE_VERIFIER_BYTES = 48  # token_urlsafe → 64 chars (RFC 7636 requires 43–128)


def _pkce_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def sso_configured(org: Organization) -> bool:
    return bool((org.sso_issuer or "").strip() and (org.sso_client_id or "").strip())


def sso_login_url(public_base_url: str | None, org_id: str) -> str | None:
    base = (public_base_url or "").rstrip("/")
    if not base:
        return None
    return f"{base}/sso/{org_id}"


def password_login_allowed(*, membership: Membership | None, org: Organization | None, is_instance_admin: bool) -> bool:
    if is_instance_admin:
        return True
    if org is None or membership is None or not sso_configured(org) or not org.sso_enabled:
        return True
    return membership.role == "org_admin"


def org_sso_public(org: Organization, *, public_base_url: str | None = None) -> dict[str, Any]:
    configured = sso_configured(org)
    return {
        "configured": configured,
        "enabled": bool(org.sso_enabled and configured),
        "login_url": sso_login_url(public_base_url, org.id) if configured else None,
    }


def org_sso_admin_public(org: Organization, *, public_base_url: str | None = None) -> dict[str, Any]:
    body = org_sso_public(org, public_base_url=public_base_url)
    base = (public_base_url or "").strip()
    body["org_id"] = org.id
    body["public_base_url_set"] = bool(base)
    if base:
        body["login_url"] = sso_login_url(public_base_url, org.id)
        body["callback_url"] = callback_url(base, org.id)
    else:
        body["login_url"] = None
        body["callback_url"] = None
    body["issuer"] = org.sso_issuer
    body["client_id"] = org.sso_client_id
    body["has_client_secret"] = bool(org.sso_client_secret_encrypted)
    return body


def _norm_issuer(issuer: str) -> str:
    return issuer.rstrip("/")


def _discovery_url(issuer: str) -> str:
    return f"{_norm_issuer(issuer)}/.well-known/openid-configuration"


def fetch_oidc_config(issuer: str) -> dict[str, Any]:
    url = _discovery_url(issuer)
    with httpx2.Client(timeout=15.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


_STATE_SIG_LEN = 32  # HMAC-SHA256 digest length; fixed suffix avoids '.' collisions in rsplit.


def _sign_state(payload: dict[str, Any]) -> str:
    from app.config import get_settings

    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(get_settings().SESSION_SECRET.encode(), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + sig).decode()


def _verify_state(state: str) -> dict[str, Any]:
    from app.config import get_settings

    try:
        blob = base64.urlsafe_b64decode(state.encode())
        if len(blob) <= _STATE_SIG_LEN:
            raise ValueError("invalid state")
        raw, sig = blob[:-_STATE_SIG_LEN], blob[-_STATE_SIG_LEN:]
    except (ValueError, binascii.Error):
        raise ValueError("invalid state") from None
    expected = hmac.new(get_settings().SESSION_SECRET.encode(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("invalid state signature")
    payload = json.loads(raw.decode())
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("state expired")
    return payload


_OAUTH_AUTHORIZE_QUERY_MAX_LEN = 2048


def make_oauth_state(org_id: str, *, oauth_authorize_query: str | None = None) -> tuple[str, str, str]:
    """Return signed state, OIDC nonce, and PKCE code_challenge (S256)."""
    nonce = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(_PKCE_VERIFIER_BYTES)
    payload = {
        "org_id": org_id,
        "nonce": nonce,
        "code_verifier": code_verifier,
        "exp": int(time.time()) + STATE_TTL_SEC,
    }
    if oauth_authorize_query:
        query = oauth_authorize_query.strip()
        if not query or len(query) > _OAUTH_AUTHORIZE_QUERY_MAX_LEN:
            raise ValueError("invalid oauth authorize query")
        payload["oauth_authorize_query"] = query
    return _sign_state(payload), nonce, _pkce_challenge(code_verifier)


def verify_oauth_state(state: str, org_id: str) -> tuple[str, str, str | None]:
    """Return OIDC nonce, PKCE code_verifier, and optional OAuth authorize query from signed state."""
    payload = _verify_state(state)
    if payload.get("org_id") != org_id:
        raise ValueError("org mismatch")
    nonce = payload.get("nonce")
    if not nonce:
        raise ValueError("missing nonce")
    code_verifier = payload.get("code_verifier")
    if not code_verifier:
        raise ValueError("missing code_verifier")
    oauth_query = payload.get("oauth_authorize_query")
    if oauth_query is not None:
        oauth_query = str(oauth_query)
    return str(nonce), str(code_verifier), oauth_query


def sso_post_login_url(public_base_url: str, *, oauth_authorize_query: str | None) -> str:
    base = public_base_url.rstrip("/")
    if oauth_authorize_query:
        return f"{base}/oauth/authorize?{oauth_authorize_query}"
    return f"{base}/app"


def begin_org_sso_login(
    *,
    org: Organization,
    public_base_url: str,
    oauth_authorize_query: str | None = None,
) -> str:
    """Build IdP authorization URL for organization SSO."""
    if not sso_configured(org):
        raise ValueError("sso_misconfigured")
    if not org.sso_enabled:
        raise ValueError("sso_disabled")
    state, nonce, code_challenge = make_oauth_state(org.id, oauth_authorize_query=oauth_authorize_query)
    return build_authorization_url(
        org=org,
        public_base_url=public_base_url,
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
    )


def callback_url(public_base_url: str, org_id: str) -> str:
    return f"{public_base_url.rstrip('/')}/api/v1/auth/sso/{org_id}/callback"


def build_authorization_url(
    *,
    org: Organization,
    public_base_url: str,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    config = fetch_oidc_config(org.sso_issuer or "")
    auth_endpoint = config["authorization_endpoint"]
    redirect_uri = callback_url(public_base_url, org.id)
    params = {
        "client_id": org.sso_client_id,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": redirect_uri,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{auth_endpoint}?{urlencode(params)}"


def _client_secret(org: Organization, db: Session) -> str | None:
    return try_decrypt_str(org.sso_client_secret_encrypted, db)


def exchange_code(
    *,
    db: Session,
    org: Organization,
    public_base_url: str,
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    config = fetch_oidc_config(org.sso_issuer or "")
    token_endpoint = config["token_endpoint"]
    redirect_uri = callback_url(public_base_url, org.id)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": org.sso_client_id,
        "code_verifier": code_verifier,
    }
    secret = _client_secret(org, db)
    auth = None
    if secret:
        auth = (org.sso_client_id or "", secret)
    with httpx2.Client(timeout=15.0) as client:
        response = client.post(token_endpoint, data=data, auth=auth)
        response.raise_for_status()
        return response.json()


def validate_id_token(*, org: Organization, id_token: str, nonce: str) -> dict[str, Any]:
    config = fetch_oidc_config(org.sso_issuer or "")
    issuer = config.get("issuer") or _norm_issuer(org.sso_issuer or "")
    jwks_uri = config["jwks_uri"]
    jwks_client = PyJWKClient(jwks_uri)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
        audience=org.sso_client_id,
        issuer=issuer,
        options={"require": ["exp", "iat", "sub"]},
    )
    if claims.get("nonce") != nonce:
        raise ValueError("nonce mismatch")
    return claims


def email_from_claims(claims: dict[str, Any]) -> str | None:
    email = claims.get("email")
    if isinstance(email, str) and "@" in email:
        return email.strip().lower()
    preferred = claims.get("preferred_username")
    if isinstance(preferred, str) and "@" in preferred:
        return preferred.strip().lower()
    return None


def resolve_or_provision_user(
    db: Session,
    *,
    org: Organization,
    email: str,
    sub: str,
    locale: str = "en",
) -> User:
    from app.timeutil import utcnow

    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        if user.disabled_at is not None:
            raise ValueError("user disabled")
        membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
        if membership is None:
            raise ValueError("user without org")
        if membership.org_id != org.id:
            raise ValueError("user wrong org")
        if user.sso_sub and user.sso_sub != sub:
            log.warning("sso sub mismatch for user %s", user.id)
        user.sso_sub = sub
        user.auth_provider = AUTH_PROVIDER_OIDC
        user.updated_at = utcnow()
        return user

    now = utcnow()
    emergency_password = random_password()
    user = User(
        id=new_id(),
        email=email,
        password_hash=hash_password(emergency_password),
        auth_provider=AUTH_PROVIDER_OIDC,
        sso_sub=sub,
        locale=locale,
        password_changed_at=now,
        must_change_password=False,
        is_instance_admin=False,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    db.add(Membership(id=new_id(), user_id=user.id, org_id=org.id, role="org_member"))
    return user


def validate_sso_config(*, issuer: str | None, client_id: str | None) -> None:
    if not issuer or not issuer.strip():
        raise ValueError("issuer required")
    if not client_id or not client_id.strip():
        raise ValueError("client_id required")
    parsed = urlparse(issuer.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("issuer must be http(s) URL")


def store_client_secret(org: Organization, secret: str | None, db: Session) -> None:
    if secret is None:
        return
    trimmed = secret.strip()
    if not trimmed:
        org.sso_client_secret_encrypted = None
        return
    org.sso_client_secret_encrypted = encrypt_str(trimmed, db)


def clear_client_secret(org: Organization) -> None:
    org.sso_client_secret_encrypted = None
