"""Auth and session API response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.me import MeResponse, UserPublic
from app.schemas.common import OkStatusResponse
from app.schemas.org_api import TariffListResponse

SignupTariffListResponse = TariffListResponse


class SetupStatusResponse(BaseModel):
    bootstrap_done: bool


class AuthUserBootstrapResponse(BaseModel):
    status: str = "ok"
    user: UserPublic


class LoginOkResponse(BaseModel):
    status: Literal["ok"] = "ok"


class LoginMfaRequiredResponse(BaseModel):
    status: Literal["mfa_required"] = "mfa_required"
    challenge_id: str


class SsoInfoResponse(BaseModel):
    org_id: str
    org_name: str
    configured: bool
    enabled: bool
    login_url: str | None = None


class MfaStatusResponse(BaseModel):
    enabled: bool
    required: bool
    enrollment_required: bool


class MfaSetupStartResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MfaSetupConfirmResponse(BaseModel):
    status: str = "ok"
    recovery_codes: list[str]


class BackupRestoreSectionReport(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0


class BackupRestoreReportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: str
    skills: BackupRestoreSectionReport | dict[str, int] | None = None
    transcripts: BackupRestoreSectionReport | dict[str, int] | None = None
    summaries: BackupRestoreSectionReport | dict[str, int] | None = None


class AccountDeleteCandidate(BaseModel):
    id: str
    email: str
    role: str


class AccountDeletePreviewResponse(BaseModel):
    requires_successor: bool
    will_delete_org: bool
    candidates: list[AccountDeleteCandidate] = Field(default_factory=list)


class AccountDeleteResultResponse(BaseModel):
    status: str = "ok"
    org_deleted: bool
    org_id: str | None = None


class ApiTokenPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    prefix: str
    revoked: bool
    blocked_by_tariff: bool
    created_at: str


class ApiTokenListResponse(BaseModel):
    items: list[ApiTokenPublic]


class ApiTokenCreateResponse(ApiTokenPublic):
    token: str


__all__ = [
    "AccountDeletePreviewResponse",
    "AccountDeleteResultResponse",
    "ApiTokenCreateResponse",
    "ApiTokenListResponse",
    "AuthUserBootstrapResponse",
    "BackupRestoreReportResponse",
    "LoginMfaRequiredResponse",
    "LoginOkResponse",
    "MeResponse",
    "MfaSetupConfirmResponse",
    "MfaSetupStartResponse",
    "MfaStatusResponse",
    "OkStatusResponse",
    "SetupStatusResponse",
    "SignupTariffListResponse",
    "SsoInfoResponse",
]
