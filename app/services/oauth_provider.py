"""OAuth 2.1 authorization server (PKCE, DCR) for MCP clients."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.deps import get_instance_settings, load_org_bundle
from app.models import (
    Membership,
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthRefreshToken,
    Organization,
    User,
    new_id,
)
from app.security import hash_secret
from app.services.oauth_keys import KID, get_private_key, get_public_jwks
from app.services.oauth_scopes import (
    SUPPORTED_SCOPES,
    normalize_scopes,
    scopes_to_string,
    validate_requested_scopes,
)
from app.services.sso import password_login_allowed
from app.timeutil import as_utc, utcnow

log = logging.getLogger("app")

PKCE_METHODS = frozenset({"S256"})


def looks_like_jwt(raw: str) -> bool:
    parts = raw.split(".")
    return len(parts) == 3 and all(parts)


def oauth_provider_enabled(settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    return bool(resolved.OAUTH_PROVIDER_ENABLED)


def public_base_url(db: Session) -> str | None:
    value = (get_instance_settings(db).public_base_url or "").strip().rstrip("/")
    return value or None


def issuer_url(db: Session) -> str | None:
    base = public_base_url(db)
    return base


def api_resource_audience(db: Session) -> str | None:
    base = public_base_url(db)
    if not base:
        return None
    return f"{base}/api/v1"


def mcp_resource_url(settings: Settings | None = None, db: Session | None = None) -> str | None:
    resolved = settings or get_settings()
    value = (resolved.OAUTH_MCP_RESOURCE_URL or "").strip().rstrip("/")
    if value:
        return value
    if db is not None:
        base = public_base_url(db)
        if base:
            return f"{base}/mcp"
    return None


def provider_ready(db: Session, settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    if not oauth_provider_enabled(resolved):
        return False
    if not public_base_url(db):
        return False
    if not mcp_resource_url(resolved, db=db):
        return False
    return True


def authorization_server_metadata(db: Session) -> dict[str, Any] | None:
    if not provider_ready(db):
        return None
    base = public_base_url(db)
    assert base is not None
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "jwks_uri": f"{base}/.well-known/jwks.json",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "scopes_supported": sorted(SUPPORTED_SCOPES),
    }


def _pkce_valid(code_verifier: str, challenge: str, method: str) -> bool:
    if method != "S256":
        return False
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(computed, challenge)


def _redirect_allowed(client: OAuthClient, redirect_uri: str) -> bool:
    return redirect_uri in (client.redirect_uris_json or [])


def get_client(db: Session, client_id: str) -> OAuthClient | None:
    return db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))


def register_client(db: Session, body: dict[str, Any]) -> tuple[OAuthClient, str | None]:
    redirect_uris = body.get("redirect_uris") or []
    if not isinstance(redirect_uris, list) or not redirect_uris:
        raise ValueError("redirect_uris required")
    for uri in redirect_uris:
        if not isinstance(uri, str) or not uri.startswith("http"):
            raise ValueError("invalid redirect_uri")
    client_name = (body.get("client_name") or "OAuth Client").strip()[:256]
    grant_types = body.get("grant_types") or ["authorization_code", "refresh_token"]
    response_types = body.get("response_types") or ["code"]
    auth_method = body.get("token_endpoint_auth_method") or "none"
    if auth_method not in {"none", "client_secret_post"}:
        raise ValueError("unsupported token_endpoint_auth_method")
    client_id = secrets.token_urlsafe(16)
    raw_secret: str | None = None
    secret_hash: str | None = None
    if auth_method == "client_secret_post":
        raw_secret = secrets.token_urlsafe(32)
        secret_hash = hash_secret(raw_secret)
    now = utcnow()
    row = OAuthClient(
        id=new_id(),
        client_id=client_id,
        client_secret_hash=secret_hash,
        client_name=client_name,
        redirect_uris_json=list(redirect_uris),
        grant_types_json=list(grant_types),
        response_types_json=list(response_types),
        token_endpoint_auth_method=auth_method,
        created_at=now,
    )
    db.add(row)
    db.flush()
    return row, raw_secret


def validate_authorize_params(
    db: Session,
    *,
    client_id: str,
    redirect_uri: str,
    response_type: str,
    scope: str | None,
    code_challenge: str,
    code_challenge_method: str,
    resource: str | None,
    settings: Settings | None = None,
) -> tuple[OAuthClient, frozenset[str], str]:
    resolved = settings or get_settings()
    if not provider_ready(db, resolved):
        raise ValueError("oauth_disabled")
    client = get_client(db, client_id)
    if client is None:
        raise ValueError("invalid_client")
    if response_type != "code":
        raise ValueError("unsupported_response_type")
    if "code" not in (client.response_types_json or []):
        raise ValueError("unsupported_response_type")
    if not _redirect_allowed(client, redirect_uri):
        raise ValueError("invalid_redirect_uri")
    if code_challenge_method not in PKCE_METHODS:
        raise ValueError("invalid_code_challenge_method")
    if not code_challenge:
        raise ValueError("invalid_code_challenge")
    expected_resource = mcp_resource_url(resolved, db=db)
    if not expected_resource:
        raise ValueError("oauth_misconfigured")
    if (resource or "").strip().rstrip("/") != expected_resource:
        raise ValueError("invalid_resource")
    scopes = validate_requested_scopes(normalize_scopes(scope))
    return client, scopes, expected_resource


_OAUTH_ORG_ROLES = frozenset({"org_admin", "org_member"})


def user_oauth_blocked(user: User, db: Session) -> str | None:
    """Return machine reason if user cannot complete OAuth / MCP."""
    from app.deps import _password_expired
    from app.services.billing import org_api_enabled
    from app.services.mfa import mfa_enrollment_required
    from app.services.user_agreement import user_agreement_required

    if user.disabled_at is not None:
        return "account_disabled"
    org, membership = load_org_bundle(db, user)
    if membership is None or org is None:
        return "oauth_org_membership_required"
    if membership.role not in _OAUTH_ORG_ROLES:
        return "forbidden"
    if user.must_change_password or _password_expired(user, org):
        return "must_change_password"
    if mfa_enrollment_required(user=user, org=org, membership=membership):
        return "mfa_enrollment_required"
    settings = get_instance_settings(db)
    if user_agreement_required(user=user, org=org, membership=membership, settings=settings):
        return "user_agreement_required"
    if org is not None and not org_api_enabled(org):
        return "api_disabled"
    return None


def issue_authorization_code(
    db: Session,
    *,
    client: OAuthClient,
    user_id: str,
    redirect_uri: str,
    scopes: frozenset[str],
    resource: str,
    code_challenge: str,
    code_challenge_method: str,
) -> str:
    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(
        OAuthAuthorizationCode(
            id=new_id(),
            code_hash=hash_secret(raw),
            client_id=client.client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            scope=scopes_to_string(scopes),
            resource=resource,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=now + timedelta(seconds=settings.OAUTH_AUTH_CODE_TTL_SEC),
            created_at=now,
        )
    )
    db.flush()
    return raw


def _audiences(db: Session, resource: str) -> list[str]:
    api_aud = api_resource_audience(db)
    audiences = [resource.rstrip("/")]
    if api_aud and api_aud not in audiences:
        audiences.append(api_aud)
    return audiences


def mint_access_token(
    db: Session,
    *,
    user_id: str,
    client_id: str,
    scopes: frozenset[str],
    resource: str,
) -> str:
    settings = get_settings()
    iss = issuer_url(db)
    if not iss:
        raise ValueError("oauth_misconfigured")
    now = int(time.time())
    payload = {
        "iss": iss,
        "sub": user_id,
        "aud": _audiences(db, resource),
        "exp": now + settings.OAUTH_ACCESS_TOKEN_TTL_SEC,
        "iat": now,
        "scope": scopes_to_string(scopes),
        "client_id": client_id,
        "azp": client_id,
    }
    private_key = get_private_key()
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})


def mint_refresh_token(
    db: Session,
    *,
    user_id: str,
    client_id: str,
    scopes: frozenset[str],
    resource: str,
) -> str:
    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(
        OAuthRefreshToken(
            id=new_id(),
            token_hash=hash_secret(raw),
            client_id=client_id,
            user_id=user_id,
            scope=scopes_to_string(scopes),
            resource=resource,
            expires_at=now + timedelta(seconds=settings.OAUTH_REFRESH_TOKEN_TTL_SEC),
            created_at=now,
        )
    )
    db.flush()
    return raw


def exchange_authorization_code(
    db: Session,
    *,
    code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str,
    client_secret: str | None,
) -> dict[str, Any]:
    client = get_client(db, client_id)
    if client is None:
        raise ValueError("invalid_client")
    if client.token_endpoint_auth_method == "client_secret_post":
        if not client_secret or hash_secret(client_secret) != client.client_secret_hash:
            raise ValueError("invalid_client")
    row = db.scalar(
        select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.code_hash == hash_secret(code))
    )
    if row is None or row.used_at is not None or as_utc(row.expires_at) <= utcnow():
        raise ValueError("invalid_grant")
    if row.client_id != client_id or row.redirect_uri != redirect_uri:
        raise ValueError("invalid_grant")
    if not _pkce_valid(code_verifier, row.code_challenge, row.code_challenge_method):
        raise ValueError("invalid_grant")
    user = db.get(User, row.user_id)
    if user is None:
        raise ValueError("invalid_grant")
    if user_oauth_blocked(user, db):
        raise ValueError("invalid_grant")
    row.used_at = utcnow()
    scopes = normalize_scopes(row.scope)
    access = mint_access_token(
        db,
        user_id=user.id,
        client_id=client_id,
        scopes=scopes,
        resource=row.resource,
    )
    refresh = mint_refresh_token(
        db,
        user_id=user.id,
        client_id=client_id,
        scopes=scopes,
        resource=row.resource,
    )
    settings = get_settings()
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": settings.OAUTH_ACCESS_TOKEN_TTL_SEC,
        "refresh_token": refresh,
        "scope": scopes_to_string(scopes),
    }


def refresh_access_token(
    db: Session,
    *,
    refresh_token: str,
    client_id: str,
    client_secret: str | None,
    resource: str | None,
) -> dict[str, Any]:
    client = get_client(db, client_id)
    if client is None:
        raise ValueError("invalid_client")
    if client.token_endpoint_auth_method == "client_secret_post":
        if not client_secret or hash_secret(client_secret) != client.client_secret_hash:
            raise ValueError("invalid_client")
    row = db.scalar(
        select(OAuthRefreshToken).where(
            OAuthRefreshToken.token_hash == hash_secret(refresh_token),
            OAuthRefreshToken.revoked_at.is_(None),
        )
    )
    if row is None or as_utc(row.expires_at) <= utcnow() or row.client_id != client_id:
        raise ValueError("invalid_grant")
    settings = get_settings()
    expected_resource = mcp_resource_url(settings, db=db)
    if resource and expected_resource and resource.rstrip("/") != expected_resource:
        raise ValueError("invalid_target")
    user = db.get(User, row.user_id)
    if user is None or user_oauth_blocked(user, db):
        raise ValueError("invalid_grant")
    scopes = normalize_scopes(row.scope)
    access = mint_access_token(
        db,
        user_id=user.id,
        client_id=client_id,
        scopes=scopes,
        resource=row.resource,
    )
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": settings.OAUTH_ACCESS_TOKEN_TTL_SEC,
        "scope": scopes_to_string(scopes),
    }


def verify_access_token(db: Session, raw: str) -> dict[str, Any] | None:
    if not oauth_provider_enabled():
        return None
    iss = issuer_url(db)
    if not iss:
        return None
    api_aud = api_resource_audience(db)
    if not api_aud:
        return None
    try:
        private_key = get_private_key()
        public_key = private_key.public_key()
        payload = jwt.decode(
            raw,
            public_key,
            algorithms=["RS256"],
            issuer=iss,
            audience=api_aud,
            options={"require": ["exp", "sub", "aud", "scope"]},
        )
    except jwt.PyJWTError:
        return None
    return payload


def authenticate_login_for_oauth(
    db: Session,
    *,
    email: str,
    password: str,
) -> User | None:
    from app.security import verify_password

    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or user.disabled_at is not None or not user.password_hash:
        return None
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
    org = db.get(Organization, membership.org_id) if membership else None

    if not password_login_allowed(
        membership=membership,
        org=org,
        is_instance_admin=user.is_instance_admin,
    ):
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def jwks_document() -> dict[str, Any]:
    return get_public_jwks()
