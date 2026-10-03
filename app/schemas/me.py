"""Session / GET /me response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.org_api import OrgPublicResponse


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    email: str
    locale: str
    default_route: str
    date_time_format: str | None = None
    timezone: str | None = None
    asr_model: str | None = None
    diarization_model: str | None = None
    tone_analytics_enabled: bool
    summarize_model: str | None = None
    capture_bot_display_name: str | None = None
    show_only_my_items: bool
    disabled: bool
    must_change_password: bool
    mfa_enabled: bool
    mfa_configured: bool | None = None
    is_instance_admin: bool
    role: str | None = None
    auth_provider: str
    user_agreement_status: str | None = None
    legal_documents_acceptance: list[dict[str, Any]] | None = None


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user: UserPublic
    org: OrgPublicResponse | None = None
    impersonating: bool
    actor: UserPublic | None = None
    date_time_prefs: dict[str, Any] = Field(default_factory=dict)
    transcribe_prefs: dict[str, Any] = Field(default_factory=dict)
    transcribe_models: dict[str, Any] = Field(default_factory=dict)
    summarize_prefs: dict[str, Any] = Field(default_factory=dict)
    summarize_models: dict[str, Any] = Field(default_factory=dict)
    capture_prefs: dict[str, Any] = Field(default_factory=dict)
    must_change_password: bool
    mfa_enabled: bool
    mfa_required: bool
    mfa_enrollment_required: bool
    user_agreement_required: bool
    user_agreement: dict[str, Any] | None = None
    user_agreement_version: int | None = None
    legal_documents: list[dict[str, Any]] | None = None
    csrf_token: str | None = None
