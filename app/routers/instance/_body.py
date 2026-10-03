"""Request bodies for instance admin routes."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.constants import MAX_UPLOAD_BYTES_CAP

class WorkerRemediation(BaseModel):
    asr_model: str | None = None
    diarization_model: str | None = None
    summarize_model: str | None = None
    capture_worker_id: str | None = None


class WorkerBody(BaseModel):
    type: str
    name: str = ""
    base_url: str
    api_token: str | None = None
    weight: int = 1
    enabled: bool = True
    asr_models: list[str] | None = None
    diarization_models: list[str] | None = None
    capture_connectors: list[str] | None = None
    remediation: WorkerRemediation | None = None


class WorkerDeleteBody(BaseModel):
    remediation: WorkerRemediation | None = None


class TariffRemediation(BaseModel):
    tariff_id: str


class TariffDeleteBody(BaseModel):
    remediation: TariffRemediation | None = None


class WorkerProbeBody(BaseModel):
    type: str
    base_url: str
    api_token: str | None = None
    worker_id: str | None = None


class TariffBody(BaseModel):
    name: str
    unlimited: bool = False
    available_on_signup: bool = False
    price_per_audio_sec: str = "0"
    price_per_summarize_job: str = "0"
    price_per_1k_summary_chars: str = "0"
    audio_retention_days: int = 0
    api_enabled: bool = True
    signup_credit: str = "0"
    max_upload_bytes: int = MAX_UPLOAD_BYTES_CAP
    tone_analytics_enabled: bool = False


class TariffCloneBody(BaseModel):
    name: str


class WalletBody(BaseModel):
    delta: str


class SmtpTestBody(BaseModel):
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_tls: bool | None = None


class SmtpTestSendBody(SmtpTestBody):
    to: str | None = None


class AgreementPreviewBody(BaseModel):
    text: str = ""


class SettingsPatch(BaseModel):
    allow_new_orgs: bool | None = None
    public_base_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_tls: bool | None = None
    asr_model: str | None = None
    diarization_model: str | None = Field(default=None)
    summarize_model: str | None = None
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
    import_enabled: bool | None = None
    import_allowed_extractors: list[str] | None = None
    capture_enabled: bool | None = None
    capture_allowed_connectors: list[str] | None = None
    download_proxy_url: str | None = None
    download_proxy_password: str | None = None
    download_proxy_enabled: bool | None = None
    download_cookies_path: str | None = None
    import_audio_bitrate_kbps: int | None = None
    import_max_concurrent: int | None = None
    session_ttl_hours: int | None = None
    task_history_retention_days: int | None = None
    date_time_format: str | None = None
    timezone: str | None = None
    user_agreement_text_en: str | None = None
    user_agreement_text_ru: str | None = None
    user_agreement_text_es: str | None = None
    personal_data_consent_text_en: str | None = None
    personal_data_consent_text_ru: str | None = None
    personal_data_consent_text_es: str | None = None
    privacy_policy_text_en: str | None = None
    privacy_policy_text_ru: str | None = None
    privacy_policy_text_es: str | None = None
    user_agreement_published: bool | None = None
    personal_data_consent_published: bool | None = None
    privacy_policy_published: bool | None = None
    landing_footer_text_en: str | None = None
    landing_footer_text_ru: str | None = None
    landing_footer_text_es: str | None = None
    landing_footer_published: bool | None = None


class CreateOrgBody(BaseModel):
    name: str
    tariff_id: str
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)
    locale: str = "en"
    is_personal: bool = False


class OrgTariffBody(BaseModel):
    tariff_id: str


class OrgDeleteBody(BaseModel):
    confirm_name: str


class OrgUserRoleBody(BaseModel):
    role: str


class ImpersonateBody(BaseModel):
    user_id: str


class BaseSkillBody(BaseModel):
    name: str
    body: str
