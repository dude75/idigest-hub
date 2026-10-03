"""Task API response models (GET /tasks)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskErrorBrief(BaseModel):
    code: str


class TaskListItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str
    type: str
    status: str
    meta: dict[str, Any] = Field(default_factory=dict)
    max_upload_bytes: int
    transcript_id: str | None = None
    summary_id: str | None = None
    error: TaskErrorBrief | None = None
    org_id: str
    user_id: str
    audio_id: str | None = None
    source_transcript_id: str | None = None
    created_at: str
    updated_at: str
    owner_email: str | None = None
    org_name: str | None = None
    audio_filename: str | None = None


class TaskListResponse(BaseModel):
    active: list[TaskListItem]
    done: list[TaskListItem]
    done_total: int
