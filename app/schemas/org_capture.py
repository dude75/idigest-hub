"""Org capture (Jitsi) API response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OrgJitsiHostPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    host: str
    jwt_app_id: str | None = None
    jwt_secret_configured: bool = False


class OrgCaptureWorkerChoice(BaseModel):
    id: str
    name: str


class OrgCaptureJitsiResponse(BaseModel):
    allowed: bool | None = None
    bot_display_name: str = ""
    items: list[OrgJitsiHostPublic] = Field(default_factory=list)
    workers: list[OrgCaptureWorkerChoice] = Field(default_factory=list)
