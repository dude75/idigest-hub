from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.constants import DEFAULT_LOCALE



class SetupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    bootstrap_token: str
    locale: str = DEFAULT_LOCALE


class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    tariff_id: str
    locale: str = DEFAULT_LOCALE
    accept_legal_documents: bool = False


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class PasswordChangeBody(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8)


class ResetRequestBody(BaseModel):
    email: EmailStr


class ResetConfirmBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class TokenCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    totp_code: str | None = None


class MfaVerifyBody(BaseModel):
    challenge_id: str
    code: str = Field(min_length=6, max_length=16)


class MfaRecoverBody(BaseModel):
    challenge_id: str
    recovery_code: str = Field(min_length=8, max_length=32)


class MfaConfirmBody(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class MfaDisableBody(BaseModel):
    password: str
    code: str = Field(min_length=6, max_length=32)


class MePatchBody(BaseModel):
    locale: str | None = None
    default_route: str | None = None
    date_time_format: str | None = None
    timezone: str | None = None
    asr_model: str | None = None
    diarization_model: str | None = Field(default=None)
    summarize_model: str | None = None
    capture_bot_display_name: str | None = None
    tone_analytics_enabled: bool | None = None


class AccountDeleteBody(BaseModel):
    password: str | None = None
    totp_code: str | None = None
    successor_user_id: str | None = None


