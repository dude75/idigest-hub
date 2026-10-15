"""User-visible name helpers (profile + SSO)."""

from __future__ import annotations

from typing import Any

from app.models import User

NAME_MAX_LEN = 128


def normalize_name_part(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = str(value).strip()
    if not trimmed:
        return None
    return trimmed[:NAME_MAX_LEN]


def user_display_name(user: User) -> str:
    parts = [p for p in (normalize_name_part(user.first_name), normalize_name_part(user.last_name)) if p]
    return " ".join(parts) if parts else user.email


def names_from_claims(claims: dict[str, Any]) -> tuple[str | None, str | None]:
    given = normalize_name_part(claims.get("given_name") if isinstance(claims.get("given_name"), str) else None)
    family = normalize_name_part(claims.get("family_name") if isinstance(claims.get("family_name"), str) else None)
    if given or family:
        return given, family
    name = claims.get("name")
    if isinstance(name, str) and name.strip():
        bits = name.strip().split(None, 1)
        first = normalize_name_part(bits[0])
        last = normalize_name_part(bits[1]) if len(bits) > 1 else None
        return first, last
    return given, family


def apply_sso_names(user: User, claims: dict[str, Any]) -> None:
    if user.profile_name_override:
        return
    first, last = names_from_claims(claims)
    user.first_name = first
    user.last_name = last
