"""Organization API response models (GET/PATCH /org)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import Tariff
from app.money import money_str, rate_str


class OrgUsageSummary(BaseModel):
    total_amount: str


class OrgSsoPublic(BaseModel):
    configured: bool
    enabled: bool
    login_url: str | None = None


class OrgSsoAdminResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    configured: bool
    enabled: bool
    login_url: str | None = None
    org_id: str
    public_base_url_set: bool
    callback_url: str | None = None
    issuer: str | None = None
    client_id: str | None = None
    has_client_secret: bool


class TariffPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    unlimited: bool
    available_on_signup: bool
    archived: bool
    price_per_audio_sec: str
    price_per_1k_summary_chars: str
    audio_retention_days: int
    api_enabled: bool
    signup_credit: str
    max_upload_bytes: int
    tone_analytics_enabled: bool
    org_count: int | None = None

    @classmethod
    def from_tariff(cls, tariff: Tariff, org_count: int | None = None) -> TariffPublic:
        payload: dict[str, object] = {
            "id": tariff.id,
            "name": tariff.name,
            "unlimited": tariff.unlimited,
            "available_on_signup": tariff.available_on_signup,
            "archived": tariff.archived_at is not None,
            "price_per_audio_sec": rate_str(Decimal(tariff.price_per_audio_sec)),
            "price_per_1k_summary_chars": rate_str(Decimal(tariff.price_per_1k_summary_chars)),
            "audio_retention_days": tariff.audio_retention_days,
            "api_enabled": tariff.api_enabled,
            "signup_credit": money_str(Decimal(tariff.signup_credit)),
            "max_upload_bytes": tariff.max_upload_bytes,
            "tone_analytics_enabled": tariff.tone_analytics_enabled,
        }
        if org_count is not None:
            payload["org_count"] = org_count
        return cls.model_validate(payload)


class TariffListResponse(BaseModel):
    items: list[TariffPublic]


class OrgPublicResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    is_personal: bool
    password_ttl_days: int
    mfa_required: bool
    balance: str
    unlimited: bool
    tariff: TariffPublic
    sso: OrgSsoPublic
    usage: OrgUsageSummary | None = None
    public_base_url_set: bool = False
    allow_public_links: bool
