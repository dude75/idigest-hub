"""Audit log API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    action: str
    actor_email: str | None = None
    on_behalf_of_email: str | None = None
    payload: dict[str, Any] | None = None
    created_at: str


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
