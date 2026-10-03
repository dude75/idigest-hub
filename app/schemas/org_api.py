"""Organization API response models (GET/PATCH /org)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
    price_per_summarize_job: str
    price_per_1k_summary_chars: str
    audio_retention_days: int
    api_enabled: bool
    signup_credit: str
    max_upload_bytes: int
    tone_analytics_enabled: bool
    org_count: int | None = None


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
