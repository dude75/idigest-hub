"""User agreement policy for org members."""

from __future__ import annotations

from app.models import InstanceSettings, Membership, Organization, User


def agreement_text(settings: InstanceSettings, locale: str) -> str:
    en = (settings.user_agreement_text_en or "").strip()
    ru = (settings.user_agreement_text_ru or "").strip()
    if locale == "ru" and ru:
        return ru
    if en:
        return en
    return ru


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
    new_en_s = (new_en or "").strip() if new_en is not None else old_en
    new_ru_s = (new_ru or "").strip() if new_ru is not None else old_ru
    changed = new_en_s != old_en or new_ru_s != old_ru

    settings.user_agreement_text_en = new_en_s or None
    settings.user_agreement_text_ru = new_ru_s or None

    if not new_en_s and not new_ru_s:
        settings.user_agreement_version = 0
    elif changed:
        had_text = bool(old_en or old_ru)
        settings.user_agreement_version = max(1, settings.user_agreement_version + 1) if had_text else 1
