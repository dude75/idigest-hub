"""Instance settings API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InstanceSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    allow_new_orgs: bool
    public_base_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_configured: bool
    smtp_password_configured: bool
    smtp_from: str | None = None
    smtp_tls: bool
    asr_model: str | None = None
    diarization_model: str | None = None
    summarize_model: str | None = None
    asr_models: list[str] = Field(default_factory=list)
    diarization_models: list[str] = Field(default_factory=list)
    summarize_models: list[str] = Field(default_factory=list)
    dispatchable_pairs: list[dict[str, Any]] | None = None
    import_enabled: bool
    import_platforms: list[dict[str, Any]] = Field(default_factory=list)
    capture_enabled: bool
    capture_connectors: list[dict[str, Any]] = Field(default_factory=list)
    download_proxy_url: str | None = None
    download_proxy_configured: bool
    download_proxy_enabled: bool
    download_cookies_path: str | None = None
    import_audio_bitrate_kbps: int
    import_max_concurrent: int
    session_ttl_hours: int
    task_history_retention_days: int
    date_time_format: str | None = None
    timezone: str | None = None
    user_agreement_text_en: str | None = None
    user_agreement_text_ru: str | None = None
    user_agreement_text_es: str | None = None
    user_agreement_version: int | None = None
    user_agreement_published: bool | None = None
    personal_data_consent_text_en: str | None = None
    personal_data_consent_text_ru: str | None = None
    personal_data_consent_text_es: str | None = None
    personal_data_consent_version: int | None = None
    personal_data_consent_published: bool | None = None
    privacy_policy_text_en: str | None = None
    privacy_policy_text_ru: str | None = None
    privacy_policy_text_es: str | None = None
    privacy_policy_version: int | None = None
    privacy_policy_published: bool | None = None
    landing_footer_text_en: str | None = None
    landing_footer_text_ru: str | None = None
    landing_footer_text_es: str | None = None
    landing_footer_published: bool | None = None
    rate_limit_enabled: bool | None = None
    rate_limit_login_email: int | None = None
    rate_limit_login_ip: int | None = None
    rate_limit_login_global: int | None = None
    rate_limit_signup_email: int | None = None
    rate_limit_signup_ip: int | None = None
    rate_limit_signup_global: int | None = None
    rate_limit_reset_email: int | None = None
    rate_limit_reset_ip: int | None = None
    rate_limit_reset_global: int | None = None
    rate_limit_reset_confirm_ip: int | None = None
    rate_limit_reset_confirm_global: int | None = None
    rate_limit_setup_ip: int | None = None
    rate_limit_setup_global: int | None = None
    rate_limit_api_user: int | None = None
    rate_limit_api_ip: int | None = None
    rate_limit_api_global: int | None = None
    rate_limit_api_tasks_user: int | None = None
    rate_limit_api_tasks_ip: int | None = None
    rate_limit_mcp_poll_user: int | None = None
    rate_limit_oauth_register_ip: int | None = None
    rate_limit_oauth_register_global: int | None = None
    rate_limit_oauth_token_ip: int | None = None
    rate_limit_oauth_token_global: int | None = None
    rate_limit_public_link_ip: int | None = None
    rate_limit_public_link_global: int | None = None
    rate_limit_public_pin_ip: int | None = None


class AgreementPreviewResponse(BaseModel):
    text: str


class LegalDocumentVersionSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: int
    published: bool
    created_at: str
    created_by_user_id: str | None = None
    created_by_email: str | None = None


class LegalDocumentVersionListResponse(BaseModel):
    key: str
    items: list[LegalDocumentVersionSummary]


class LegalDocumentVersionDetailResponse(LegalDocumentVersionSummary):
    key: str
    text_en: str | None = None
    text_ru: str | None = None
    text_es: str | None = None


class SmtpTestSendResponse(BaseModel):
    status: str = "ok"
    to: str
