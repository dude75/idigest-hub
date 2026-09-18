"""Legal documents policy for org members."""

from __future__ import annotations

import re
from typing import Literal

from app.models import InstanceSettings, Membership, Organization, User

LegalDocumentKey = Literal["user_agreement", "personal_data_consent", "privacy_policy"]

LEGAL_DOCUMENT_KEYS: tuple[LegalDocumentKey, ...] = (
    "user_agreement",
    "personal_data_consent",
    "privacy_policy",
)

LEGAL_DOCUMENT_SPECS: dict[LegalDocumentKey, dict[str, str]] = {
    "user_agreement": {
        "text_en": "user_agreement_text_en",
        "text_ru": "user_agreement_text_ru",
        "version": "user_agreement_version",
        "published": "user_agreement_published",
        "accepted": "user_agreement_accepted_version",
    },
    "personal_data_consent": {
        "text_en": "personal_data_consent_text_en",
        "text_ru": "personal_data_consent_text_ru",
        "version": "personal_data_consent_version",
        "published": "personal_data_consent_published",
        "accepted": "personal_data_consent_accepted_version",
    },
    "privacy_policy": {
        "text_en": "privacy_policy_text_en",
        "text_ru": "privacy_policy_text_ru",
        "version": "privacy_policy_version",
        "published": "privacy_policy_published",
        "accepted": "privacy_policy_accepted_version",
    },
}

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


def _setting_text(settings: InstanceSettings, key: LegalDocumentKey, locale: str) -> str:
    spec = LEGAL_DOCUMENT_SPECS[key]
    en = (getattr(settings, spec["text_en"]) or "").strip()
    ru = (getattr(settings, spec["text_ru"]) or "").strip()
    if locale == "ru" and ru:
        return normalize_agreement_markdown(ru)
    if en:
        return normalize_agreement_markdown(en)
    return normalize_agreement_markdown(ru) if ru else ru


def document_text(settings: InstanceSettings, key: LegalDocumentKey, locale: str) -> str:
    return _setting_text(settings, key, locale)


def agreement_text(settings: InstanceSettings, locale: str) -> str:
    return document_text(settings, "user_agreement", locale)


def document_published(settings: InstanceSettings, key: LegalDocumentKey) -> bool:
    spec = LEGAL_DOCUMENT_SPECS[key]
    return bool(getattr(settings, spec["published"]))


def document_active(settings: InstanceSettings, key: LegalDocumentKey) -> bool:
    spec = LEGAL_DOCUMENT_SPECS[key]
    version = getattr(settings, spec["version"])
    if version <= 0:
        return False
    en = (getattr(settings, spec["text_en"]) or "").strip()
    ru = (getattr(settings, spec["text_ru"]) or "").strip()
    return bool(en or ru)


def agreement_active(settings: InstanceSettings) -> bool:
    return document_active(settings, "user_agreement")


def any_document_active(settings: InstanceSettings) -> bool:
    return any(document_active(settings, key) for key in LEGAL_DOCUMENT_KEYS)


def document_pending(user: User, settings: InstanceSettings, key: LegalDocumentKey) -> bool:
    if not document_active(settings, key):
        return False
    spec = LEGAL_DOCUMENT_SPECS[key]
    accepted = getattr(user, spec["accepted"]) or 0
    version = getattr(settings, spec["version"])
    return accepted < version


def pending_legal_document_keys(user: User, settings: InstanceSettings) -> list[LegalDocumentKey]:
    return [key for key in LEGAL_DOCUMENT_KEYS if document_pending(user, settings, key)]


def member_legal_documents(user: User, settings: InstanceSettings, locale: str) -> list[dict]:
    docs: list[dict] = []
    for key in LEGAL_DOCUMENT_KEYS:
        if not document_active(settings, key):
            continue
        spec = LEGAL_DOCUMENT_SPECS[key]
        accepted = getattr(user, spec["accepted"]) or 0
        version = getattr(settings, spec["version"])
        docs.append(
            {
                "key": key,
                "version": version,
                "text": document_text(settings, key, locale),
                "accepted_version": accepted,
                "pending": accepted < version,
            }
        )
    return docs


def accept_all_pending_documents(user: User, settings: InstanceSettings) -> list[LegalDocumentKey]:
    accepted: list[LegalDocumentKey] = []
    for key in pending_legal_document_keys(user, settings):
        spec = LEGAL_DOCUMENT_SPECS[key]
        setattr(user, spec["accepted"], getattr(settings, spec["version"]))
        accepted.append(key)
    return accepted


def agreement_acceptance_status(user: User, settings: InstanceSettings) -> str | None:
    if not any(document_active(settings, key) for key in LEGAL_DOCUMENT_KEYS):
        return None
    if pending_legal_document_keys(user, settings):
        return "pending"
    return "accepted"


def user_agreement_required(
    *,
    user: User,
    org: Organization | None,
    membership: Membership | None,
    settings: InstanceSettings,
) -> bool:
    if membership is None or org is None:
        return False
    return bool(pending_legal_document_keys(user, settings))


def _apply_document_text_patch(settings: InstanceSettings, key: LegalDocumentKey, data: dict) -> None:
    spec = LEGAL_DOCUMENT_SPECS[key]
    en_field = spec["text_en"]
    ru_field = spec["text_ru"]
    version_field = spec["version"]

    new_en = data.pop(en_field) if en_field in data else getattr(settings, en_field)
    new_ru = data.pop(ru_field) if ru_field in data else getattr(settings, ru_field)

    old_en = (getattr(settings, en_field) or "").strip()
    old_ru = (getattr(settings, ru_field) or "").strip()
    new_en_s = normalize_agreement_markdown((new_en or "").strip()) if new_en is not None else old_en
    new_ru_s = normalize_agreement_markdown((new_ru or "").strip()) if new_ru is not None else old_ru
    changed = new_en_s != old_en or new_ru_s != old_ru

    setattr(settings, en_field, new_en_s or None)
    setattr(settings, ru_field, new_ru_s or None)

    if not new_en_s and not new_ru_s:
        setattr(settings, version_field, 0)
    elif changed:
        had_text = bool(old_en or old_ru)
        current_version = getattr(settings, version_field)
        setattr(settings, version_field, max(1, current_version + 1) if had_text else 1)


def apply_agreement_text_patch(settings: InstanceSettings, data: dict) -> None:
    _apply_document_text_patch(settings, "user_agreement", data)


def apply_legal_documents_patch(settings: InstanceSettings, data: dict) -> None:
    for key in LEGAL_DOCUMENT_SPECS:
        spec = LEGAL_DOCUMENT_SPECS[key]
        if spec["text_en"] in data or spec["text_ru"] in data:
            _apply_document_text_patch(settings, key, data)
    apply_landing_footer_patch(settings, data)


def landing_footer_text(settings: InstanceSettings, locale: str) -> str:
    en = (settings.landing_footer_text_en or "").strip()
    ru = (settings.landing_footer_text_ru or "").strip()
    if locale == "ru" and ru:
        return normalize_agreement_markdown(ru)
    if en:
        return normalize_agreement_markdown(en)
    return normalize_agreement_markdown(ru) if ru else ""


def apply_landing_footer_patch(settings: InstanceSettings, data: dict) -> None:
    if "landing_footer_text_en" in data:
        raw = data.pop("landing_footer_text_en")
        text = normalize_agreement_markdown((raw or "").strip()) if raw is not None else ""
        settings.landing_footer_text_en = text or None
    if "landing_footer_text_ru" in data:
        raw = data.pop("landing_footer_text_ru")
        text = normalize_agreement_markdown((raw or "").strip()) if raw is not None else ""
        settings.landing_footer_text_ru = text or None


def public_landing_footer_text(settings: InstanceSettings, locale: str) -> str | None:
    if not settings.landing_footer_published:
        return None
    text = landing_footer_text(settings, locale)
    return text or None


def public_legal_documents(settings: InstanceSettings, locale: str) -> list[dict]:
    docs: list[dict] = []
    for key in LEGAL_DOCUMENT_KEYS:
        if not document_active(settings, key) or not document_published(settings, key):
            continue
        spec = LEGAL_DOCUMENT_SPECS[key]
        docs.append(
            {
                "key": key,
                "version": getattr(settings, spec["version"]),
                "text": document_text(settings, key, locale),
            }
        )
    return docs
