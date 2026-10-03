"""Instance encryption (DEK / reencrypt) API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import OkStatusResponse


class DekPublicResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    status: str
    created_at: str
    retired_at: str | None = None
    usage_count: int


class DekListResponse(BaseModel):
    active_dek_id: str | None = None
    items: list[DekPublicResponse] = Field(default_factory=list)
    running_job_id: str | None = None
    deks_pending_rewrap: int
    hub_secret_prev_configured: bool
    reencrypt_available: bool


class EncryptionJobPublicResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    target_dek_id: str | None = None
    status: str
    progress: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str


class EncryptionJobLatestResponse(BaseModel):
    job: EncryptionJobPublicResponse | None = None
