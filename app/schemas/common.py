"""Shared minimal API response models."""

from __future__ import annotations

from pydantic import BaseModel


class OkStatusResponse(BaseModel):
    status: str = "ok"
