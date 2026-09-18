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

LEGAL_DOCUMENT_TEXT_FIELDS = ("text_en", "text_ru", "text_es")

LEGAL_DOCUMENT_SPECS: dict[LegalDocumentKey, dict[str, str]] = {
    "user_agreement": {
        "text_en": "user_agreement_text_en",
        "text_ru": "user_agreement_text_ru",
        "text_es": "user_agreement_text_es",
        "version": "user_agreement_version",
        "published": "user_agreement_published",
        "accepted": "user_agreement_accepted_version",
    },
    "personal_data_consent": {
        "text_en": "personal_data_consent_text_en",
        "text_ru": "personal_data_consent_text_ru",
        "text_es": "personal_data_consent_text_es",
        "version": "personal_data_consent_version",
        "published": "personal_data_consent_published",
        "accepted": "personal_data_consent_accepted_version",
    },
    "privacy_policy": {
        "text_en": "privacy_policy_text_en",
        "text_ru": "privacy_policy_text_ru",
        "text_es": "privacy_policy_text_es",
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


def _localized_markdown(*, locale: str, en: str, ru: str, es: str) -> str:
    en = (en or "").strip()
    ru = (ru or "").strip()
    es = (es or "").strip()
    if locale == "ru" and ru:
        return normalize_agreement_markdown(ru)
    if locale == "es" and es:
        return normalize_agreement_markdown(es)
    if en:
        return normalize_agreement_markdown(en)
    if ru:
        return normalize_agreement_markdown(ru)
    if es:
        return normalize_agreement_markdown(es)
    return ""


def _setting_text(settings: InstanceSettings, key: LegalDocumentKey, locale: str) -> str:
    spec = LEGAL_DOCUMENT_SPECS[key]
    return _localized_markdown(
        locale=locale,
        en=getattr(settings, spec["text_en"]) or "",
        ru=getattr(settings, spec["text_ru"]) or "",
        es=getattr(settings, spec["text_es"]) or "",
    )


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
    return any(
        (getattr(settings, spec[field]) or "").strip() for field in LEGAL_DOCUMENT_TEXT_FIELDS
    )


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
    version_field = spec["version"]
    text_fields = [spec[field] for field in LEGAL_DOCUMENT_TEXT_FIELDS]

    old_values = [(getattr(settings, field) or "").strip() for field in text_fields]
    new_values: list[str] = []
    for field in text_fields:
        raw = data.pop(field) if field in data else getattr(settings, field)
        if raw is None:
            new_values.append((getattr(settings, field) or "").strip())
        else:
            new_values.append(normalize_agreement_markdown((raw or "").strip()))

    changed = new_values != old_values
    for field, value in zip(text_fields, new_values, strict=True):
        setattr(settings, field, value or None)

    if not any(new_values):
        setattr(settings, version_field, 0)
    elif changed:
        had_text = bool(any(old_values))
        current_version = getattr(settings, version_field)
        setattr(settings, version_field, max(1, current_version + 1) if had_text else 1)


def apply_agreement_text_patch(settings: InstanceSettings, data: dict) -> None:
    _apply_document_text_patch(settings, "user_agreement", data)


def apply_legal_documents_patch(settings: InstanceSettings, data: dict) -> None:
    for key in LEGAL_DOCUMENT_SPECS:
        spec = LEGAL_DOCUMENT_SPECS[key]
        if any(spec[field] in data for field in LEGAL_DOCUMENT_TEXT_FIELDS):
            _apply_document_text_patch(settings, key, data)
    apply_landing_footer_patch(settings, data)


def landing_footer_text(settings: InstanceSettings, locale: str) -> str:
    return _localized_markdown(
        locale=locale,
        en=settings.landing_footer_text_en or "",
        ru=settings.landing_footer_text_ru or "",
        es=settings.landing_footer_text_es or "",
    )


def apply_landing_footer_patch(settings: InstanceSettings, data: dict) -> None:
    if "landing_footer_text_en" in data:
        raw = data.pop("landing_footer_text_en")
        text = normalize_agreement_markdown((raw or "").strip()) if raw is not None else ""
        settings.landing_footer_text_en = text or None
    if "landing_footer_text_ru" in data:
        raw = data.pop("landing_footer_text_ru")
        text = normalize_agreement_markdown((raw or "").strip()) if raw is not None else ""
        settings.landing_footer_text_ru = text or None
    if "landing_footer_text_es" in data:
        raw = data.pop("landing_footer_text_es")
        text = normalize_agreement_markdown((raw or "").strip()) if raw is not None else ""
        settings.landing_footer_text_es = text or None


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
