"""Worker admin API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import OkStatusResponse


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


class WorkerEngineOption(BaseModel):
    id: str
    status: str
    label: str | None = None


class WorkerProbeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    authorized: bool
    health_status: int
    asr_models: list[WorkerEngineOption] | None = None
    diarization_models: list[WorkerEngineOption] | None = None
    connectors: list[WorkerEngineOption] | None = None
    summarize_model: str | None = None


class WorkerImpactResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str | None = None
    worker: dict[str, Any]
    blocking: bool
    can_remediate: bool | None = None
    remaining_transcribe_workers: int | None = None
    lost_model_pairs: list[dict[str, str]] = Field(default_factory=list)
    available_pairs: list[dict[str, str]] | None = None
    suggested_replacement: dict[str, str] | None = None
    instance_defaults_broken: bool | None = None
    instance_defaults: dict[str, Any] | None = None
    affected_users: list[dict[str, Any]] = Field(default_factory=list)
    affected_users_count: int | None = None
    affected_tasks: list[dict[str, Any]] = Field(default_factory=list)
    affected_tasks_count: int | None = None
    remaining_summarize_workers: int | None = None
    last_enabled_worker: bool | None = None
    lost_summarize_models: list[str] | None = None
    available_summarize_models: list[dict[str, str]] | None = None
    suggested_summarize_replacement: dict[str, str] | None = None
    capture_jitsi_hosts: list[Any] = Field(default_factory=list)
    capture_jitsi_hosts_count: int | None = None
    capture_tasks_count: int | None = None
    capture_losing_jitsi: bool | None = None
    available_capture_workers: list[dict[str, Any]] | None = None
    suggested_capture_worker: dict[str, Any] | None = None


class WorkerDeleteResponse(OkStatusResponse):
    model_config = ConfigDict(extra="ignore")

    remediation: dict[str, Any] | None = None
    cleanup: dict[str, Any] | None = None


class InstanceTranscribeModelsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    asr_models: list[str] = Field(default_factory=list)
    diarization_models: list[str] = Field(default_factory=list)
    dispatchable_pairs: list[dict[str, Any]] | None = None
    default_asr_model: str | None = None
    default_diarization_model: str | None = None


class InstanceSummarizeModelsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summarize_models: list[str] = Field(default_factory=list)
    default_summarize_model: str | None = None
