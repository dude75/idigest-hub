"""Session cookie."""

from __future__ import annotations

from datetime import timedelta

from fastapi import Response

from app.config import get_settings
from app.constants import COOKIE_NAME, SESSION_TTL_SEC


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


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def sliding_cookie(response: Response, token: str | None, *, max_age: int = SESSION_TTL_SEC) -> None:
    if token:
        set_session_cookie(response, token, max_age=max_age)
