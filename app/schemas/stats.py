"""Usage statistics API response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class UsageStatsDay(BaseModel):
    date: str
    tasks_transcribe_success: int
    tasks_summarize_success: int
    audio_transcribed_sec: float
    summary_chars: int
    amount: str


class UsageStatsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tasks_transcribe_success: int
    tasks_summarize_success: int
    audio_transcribed_sec: float
    summary_chars: int
    total_amount: str
    days: list[UsageStatsDay]


class InstanceUsageStatsResponse(UsageStatsResponse):
    orgs: int
    users: int
    tasks_queued: int
    tasks_running: int
    download_proxy_status: Literal["up", "down", "na"]
    usage_total: str
