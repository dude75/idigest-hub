"""Organization user list/admin response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.me import UserPublic


class OrgUserListResponse(BaseModel):
    items: list[UserPublic]


class OrgUserResetPasswordResponse(BaseModel):
    status: str = "ok"
    password: str


class OffboardStatusResponse(BaseModel):
    status: str = "ok"
