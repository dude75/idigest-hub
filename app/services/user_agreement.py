"""User agreement policy for org members."""

from __future__ import annotations

import re

from app.models import InstanceSettings, Membership, Organization, User

_FENCE_FULL = re.compile(r"^```(?:markdown|md)?\r?\n([\s\S]*?)\r?\n```$")
_FENCE_OPEN = re.compile(r"^```(?:markdown|md)?\r?\n([\s\S]*)$")
_GLUED_TABLE = re.compile(r"^([^\n]*[^\n|])(\|(?:[^|\n]+\|){2,}.*)$", re.MULTILINE)


def normalize_agreement_markdown(text: str) -> str:
    """Fix common chat-paste issues so GFM tables and blockquotes parse reliably."""
    body = text.strip()
    if not body:
        return body
    fence = _FENCE_FULL.match(body)
    if fence:
        body = fence.group(1)
    else:
        open_fence = _FENCE_OPEN.match(body)
        if open_fence:
            body = open_fence.group(1).rstrip()
    body = re.sub(r"\|{2,}", "|", body)
    body = re.sub(r"^\|\s+([^|\n]+)$", r"> \1", body, flags=re.MULTILINE)

    def _split_glued(match: re.Match[str]) -> str:
        prefix, table = match.group(1), match.group(2)
        if prefix.lstrip().startswith("|"):
            return match.group(0)
        return f"{prefix.rstrip()}\n\n{table}"

    body = _GLUED_TABLE.sub(_split_glued, body)
    body = re.sub(r"\|\s+\|", "|\n|", body)
    body = _GLUED_TABLE.sub(_split_glued, body)
    return body


def agreement_text(settings: InstanceSettings, locale: str) -> str:
    en = (settings.user_agreement_text_en or "").strip()
    ru = (settings.user_agreement_text_ru or "").strip()
    if locale == "ru" and ru:
        return normalize_agreement_markdown(ru)
    if en:
        return normalize_agreement_markdown(en)
    return normalize_agreement_markdown(ru) if ru else ru


def agreement_active(settings: InstanceSettings) -> bool:
    if settings.user_agreement_version <= 0:
        return False
    en = (settings.user_agreement_text_en or "").strip()
    ru = (settings.user_agreement_text_ru or "").strip()
    return bool(en or ru)


def agreement_acceptance_status(user: User, settings: InstanceSettings) -> str | None:
    if not agreement_active(settings):
        return None
    accepted = user.user_agreement_accepted_version or 0
    if accepted >= settings.user_agreement_version:
        return "accepted"
    return "pending"


def user_agreement_required(
    *,
    user: User,
    org: Organization | None,
    membership: Membership | None,
    settings: InstanceSettings,
) -> bool:
    if membership is None or org is None:
        return False
    if not agreement_active(settings):
        return False
    accepted = user.user_agreement_accepted_version or 0
    return accepted < settings.user_agreement_version


def apply_agreement_text_patch(settings: InstanceSettings, data: dict) -> None:
    new_en = data.pop("user_agreement_text_en") if "user_agreement_text_en" in data else settings.user_agreement_text_en
    new_ru = data.pop("user_agreement_text_ru") if "user_agreement_text_ru" in data else settings.user_agreement_text_ru

    old_en = (settings.user_agreement_text_en or "").strip()
    old_ru = (settings.user_agreement_text_ru or "").strip()
    new_en_s = normalize_agreement_markdown((new_en or "").strip()) if new_en is not None else old_en
    new_ru_s = normalize_agreement_markdown((new_ru or "").strip()) if new_ru is not None else old_ru
    changed = new_en_s != old_en or new_ru_s != old_ru

    settings.user_agreement_text_en = new_en_s or None
    settings.user_agreement_text_ru = new_ru_s or None

    if not new_en_s and not new_ru_s:
        settings.user_agreement_version = 0
    elif changed:
        had_text = bool(old_en or old_ru)
        settings.user_agreement_version = max(1, settings.user_agreement_version + 1) if had_text else 1
