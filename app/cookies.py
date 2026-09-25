"""Session and CSRF cookies."""

from __future__ import annotations

from fastapi import Request, Response

from app.config import get_settings
from app.constants import COOKIE_NAME, CSRF_COOKIE_NAME, SESSION_TTL_SEC
from app.security import new_session_token


def set_session_cookie(
    response: Response,
    token: str,
    *,
    max_age: int = SESSION_TTL_SEC,
    samesite: str = "lax",
) -> None:
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=samesite,
        secure=settings.COOKIE_SECURE,
        max_age=max_age,
        path="/",
    )


def set_csrf_cookie(
    response: Response,
    token: str,
    *,
    max_age: int = SESSION_TTL_SEC,
    samesite: str = "lax",
) -> None:
    settings = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        samesite=samesite,
        secure=settings.COOKIE_SECURE,
        max_age=max_age,
        path="/",
    )


def issue_auth_cookies(
    response: Response,
    session_token: str,
    *,
    max_age: int = SESSION_TTL_SEC,
    samesite: str = "lax",
) -> None:
    set_session_cookie(response, session_token, max_age=max_age, samesite=samesite)
    set_csrf_cookie(response, new_session_token(), max_age=max_age, samesite=samesite)


def oauth_embedded_session_samesite() -> str:
    """SameSite for MCP/OAuth browser login (iframe / cross-site return from IdP)."""
    settings = get_settings()
    if not settings.COOKIE_SECURE:
        return "lax"
    from app.services.oauth_provider import oauth_provider_enabled

    return "none" if oauth_provider_enabled() else "lax"


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def clear_auth_cookies(response: Response) -> None:
    clear_session_cookie(response)
    clear_csrf_cookie(response)


def ensure_csrf_cookie(response: Response, *, has_session: bool, csrf_present: bool, max_age: int = SESSION_TTL_SEC) -> None:
    """Backfill CSRF for sessions created before CSRF cookies were introduced."""
    if has_session and not csrf_present:
        set_csrf_cookie(response, new_session_token(), max_age=max_age)


def response_sets_csrf_cookie(response: Response) -> bool:
    for key, value in response.raw_headers:
        if key.lower() == b"set-cookie" and CSRF_COOKIE_NAME.encode() in value:
            return True
    return False


def bind_csrf_token(request: Request, response: Response, *, max_age: int = SESSION_TTL_SEC) -> str:
    """Ensure hub_csrf cookie on the response and return the token for the SPA header."""
    token = (request.cookies.get(CSRF_COOKIE_NAME) or "").strip()
    if not token:
        token = new_session_token()
        set_csrf_cookie(response, token, max_age=max_age)
    return token


def sliding_cookie(response: Response, token: str | None, *, max_age: int = SESSION_TTL_SEC) -> None:
    if token:
        set_session_cookie(response, token, max_age=max_age)
