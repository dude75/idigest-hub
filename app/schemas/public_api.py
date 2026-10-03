"""Unauthenticated public API response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PublicLegalDocumentItem(BaseModel):
    key: str
    version: int
    text: str


class PublicLegalDocumentsResponse(BaseModel):
    items: list[PublicLegalDocumentItem] = Field(default_factory=list)
    footer_text: str | None = None


class PublicLegalDocumentDetailResponse(BaseModel):
    key: str
    version: int
    text: str


class PublicSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pin_required: bool
    title: str | None = None
    display_title: str | None = None
    body: str | None = None
