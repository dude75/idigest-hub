"""Share API response models."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.library import ShareRecordBrief


class ShareListResponse(BaseModel):
    items: list[ShareRecordBrief]


class ShareCreateResponse(BaseModel):
    ids: list[str]


class OkStatusResponse(BaseModel):
    status: str = "ok"
