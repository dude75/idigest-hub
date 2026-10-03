"""Worker admin API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkerPublicResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    type: str
    name: str
    base_url: str
    weight: int
    enabled: bool
    last_health: dict[str, Any] | None = None
    last_seen_version: str | None = None
    last_health_at: str | None = None
    asr_models: list[str] = Field(default_factory=list)
    diarization_models: list[str] = Field(default_factory=list)
    capture_connectors: list[str] = Field(default_factory=list)
    summarize_model: str | None = None


class WorkerListItem(WorkerPublicResponse):
    dispatch_available: bool


class WorkersTypeSummary(BaseModel):
    total: int
    enabled: int
    available: int


class WorkersByTypeSummary(BaseModel):
    transcribe: WorkersTypeSummary
    summarize: WorkersTypeSummary
    capture: WorkersTypeSummary


class WorkerCapacitySummary(BaseModel):
    max: int
    active: int
    available: int


class WorkersHubLimits(BaseModel):
    import_max_concurrent: int


class WorkersListSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total: int
    enabled: int
    available: int
    by_type: WorkersByTypeSummary
    hub_limits: WorkersHubLimits
    capture_capacity: WorkerCapacitySummary
    transcribe_capacity: WorkerCapacitySummary
    summarize_capacity: WorkerCapacitySummary


class WorkerListResponse(BaseModel):
    items: list[WorkerListItem]
    summary: WorkersListSummary


class WorkerMutateResponse(WorkerPublicResponse):
    model_config = ConfigDict(extra="ignore")

    remediation: dict[str, Any] | None = None
