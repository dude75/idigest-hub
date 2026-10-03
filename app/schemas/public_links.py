"""Public link list API response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OrgPublicLinkItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    summary_id: str
    url: str | None = None
    expires_at: str | None = None
    pin_required: bool
    created_at: str
    revoked: bool
    summary_title: str | None = None
    owner_email: str | None = None
    active: bool


class OrgPublicLinkListResponse(BaseModel):
    items: list[OrgPublicLinkItem]
