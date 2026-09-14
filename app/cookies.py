"""Session and CSRF cookies."""

from __future__ import annotations

from fastapi import Response

from app.config import get_settings
from app.constants import COOKIE_NAME, CSRF_COOKIE_NAME, SESSION_TTL_SEC
from app.security import new_session_token


def set_session_cookie(response: Response, token: str, *, max_age: int = SESSION_TTL_SEC) -> None:
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=max_age,
        path="/",
    )


def set_csrf_cookie(response: Response, token: str, *, max_age: int = SESSION_TTL_SEC) -> None:
    settings = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=max_age,
        path="/",
    )


def issue_auth_cookies(response: Response, session_token: str, *, max_age: int = SESSION_TTL_SEC) -> None:
    set_session_cookie(response, session_token, max_age=max_age)
    set_csrf_cookie(response, new_session_token(), max_age=max_age)


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def clear_auth_cookies(response: Response) -> None:
    clear_session_cookie(response)
    clear_csrf_cookie(response)


def sliding_cookie(response: Response, token: str | None, *, max_age: int = SESSION_TTL_SEC) -> None:
    if token:
        set_session_cookie(response, token, max_age=max_age)
