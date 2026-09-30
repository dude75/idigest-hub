"""Локализованные сообщения для ошибок валидации тела/query (Pydantic / FastAPI)."""

from __future__ import annotations

from typing import Any

from fastapi.exceptions import RequestValidationError

from app.i18n import t

_LOC_SKIP = frozenset({"body", "query", "path", "header", "cookie"})


def _field_name(loc: tuple[Any, ...]) -> str | None:
    for part in reversed(loc):
        if isinstance(part, str) and part not in _LOC_SKIP:
            return part
    return None


def _message_for_error(locale: str, err: dict[str, Any]) -> str | None:
    field = _field_name(tuple(err.get("loc") or ()))
    err_type = str(err.get("type") or "")

    if field == "email" and err_type in {"value_error", "string_type"}:
        return t(locale, "invalid_email")
    if field == "password" and err_type == "string_too_short":
        ctx = err.get("ctx") or {}
        min_len = ctx.get("min_length", 8)
        return t(locale, "password_too_short", min=min_len)
    if err_type == "missing" and field == "email":
        return t(locale, "invalid_email")
    if err_type == "missing" and field == "password":
        return t(locale, "password_too_short", min=8)
    return None


def validation_error_message(locale: str, exc: RequestValidationError) -> str:
    messages: list[str] = []
    seen: set[str] = set()
    for err in exc.errors():
        msg = _message_for_error(locale, err)
        if msg is None:
            continue
        if msg in seen:
            continue
        seen.add(msg)
        messages.append(msg)
    if messages:
        return " ".join(messages)
    return t(locale, "validation_error")
