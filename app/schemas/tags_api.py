"""User tag API response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import OkStatusResponse
from app.schemas.library import UserTagBrief


class UserTagListResponse(BaseModel):
    items: list[UserTagBrief] = Field(default_factory=list)


class UserTagPublicResponse(UserTagBrief):
    pass


class ObjectTagsResponse(BaseModel):
    tags: list[UserTagBrief] = Field(default_factory=list)
