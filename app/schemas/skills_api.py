"""Skill catalog API response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import OkStatusResponse


class SkillPublicResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    scope: str
    org_id: str | None = None
    owner_user_id: str | None = None
    name: str
    body: str
    created_at: str
    updated_at: str
    catalog: str | None = None
    readonly: bool | None = None
    share_kind: str | None = None
    shared_by: str | None = None
    share_id: str | None = None


class SkillListResponse(BaseModel):
    items: list[SkillPublicResponse] = Field(default_factory=list)
