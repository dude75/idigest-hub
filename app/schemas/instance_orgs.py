"""Instance admin org list / ledger response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.me import UserPublic
from app.schemas.org_api import OrgPublicResponse
from app.schemas.org_users import OrgUserResetPasswordResponse


class InstanceOrgListItem(OrgPublicResponse):
    hidden: bool = False
    members: list[UserPublic] = Field(default_factory=list)


class InstanceOrgListResponse(BaseModel):
    items: list[InstanceOrgListItem]
    hidden_count: int


class InstanceOrgCreateResponse(OrgPublicResponse):
    members: list[UserPublic] = Field(default_factory=list)


class OrgLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    entry_type: str
    created_at: str
    amount: str
    usage_amount: str | None = None
    kind: str | None = None
    user_id: str | None = None
    user_email: str | None = None
    task_id: str | None = None
    actor_email: str | None = None
    unlimited_skip: bool
    audio_sec: float | None = None
    summary_chars: int | None = None


class OrgLedgerResponse(BaseModel):
    items: list[OrgLedgerEntry]
    total_spent: str
    total_topup: str
    net: str
