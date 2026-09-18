"""CSRF protection for cookie-authenticated API mutations (double-submit cookie)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.constants import COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.errors import ErrorCode, error_payload
from app.i18n import negotiate_locale, t
from app.security import compare_digest

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Public POST endpoints that establish auth or run before a session exists.
CSRF_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/setup",
        "/api/v1/auth/signup",
        "/api/v1/auth/login",
        "/api/v1/auth/mfa/verify",
        "/api/v1/auth/mfa/recover",
        "/api/v1/auth/password/reset/request",
        "/api/v1/auth/password/reset/confirm",
    }
)
CSRF_EXEMPT_PREFIXES: tuple[str, ...] = ("/api/v1/public/summary/",)


def csrf_required(request: Request) -> bool:
    if request.method not in _UNSAFE_METHODS:
        return False
    path = request.url.path.rstrip("/") or "/"
    if not path.startswith("/api/v1"):
        return False
    authorization = (request.headers.get("authorization") or "").lower()
    if authorization.startswith("bearer "):
        return False
    if path in CSRF_EXEMPT_PATHS:
        return False
    if any(path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES):
        return False
    if not request.cookies.get(COOKIE_NAME):
        return False
    return True


async def enforce_csrf(request: Request) -> JSONResponse | None:
    if not csrf_required(request):
        return None
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME) or ""
    header_token = request.headers.get(CSRF_HEADER_NAME) or ""
    if not cookie_token or not header_token or not compare_digest(cookie_token, header_token):
        locale = negotiate_locale(request.headers.get("accept-language"))
        return JSONResponse(
            status_code=403,
            content=error_payload(ErrorCode.csrf_invalid, t(locale, ErrorCode.csrf_invalid.value)),
        )
    return None
