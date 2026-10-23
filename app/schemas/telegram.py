"""Telegram link API models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MeTelegramStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bot_enabled: bool
    bot_username: str | None = None
    bot_url: str | None = None
    linked: bool
    linked_at: str | None = None


class MeTelegramLinkResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    expires_at: str
    start_command: str
    bot_username: str | None = None
    bot_url: str | None = None
