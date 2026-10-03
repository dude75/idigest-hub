"""Library list and detail API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ShareBody(BaseModel):
    object_type: str
    object_id: str
    to_user_ids: list[str]


class TitlePatch(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class SummaryPatch(BaseModel):
    body: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)


class SummaryPublicLinkBody(BaseModel):
    expires_in_days: int | None = Field(default=7)
    pin: str | None = None


class UserTagBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    usage_count: int | None = None


class ShareRecordBrief(BaseModel):
    id: str
    to_user_id: str
    email: str


class LibraryShareFields(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hidden: bool = False
    owner_email: str | None = None
    user_tags: list[UserTagBrief] = Field(default_factory=list)
    share_kind: str | None = None
    shared_by: str | None = None
    shared_with: list[str] | None = None
    shares: list[ShareRecordBrief] | None = None
    share_id: str | None = None


class AudioListItem(LibraryShareFields):
    id: str
    org_id: str
    owner_user_id: str
    filename: str
    source_url: str | None = None
    duration_sec: float | None = None
    created_at: str
    has_transcript: bool = False
    has_summary: bool = False
    transcript_id: str | None = None
    summary_transcript_id: str | None = None


class AudioListResponse(BaseModel):
    items: list[AudioListItem]
    total: int
    hidden_count: int


class TranscriptListItem(LibraryShareFields):
    id: str
    org_id: str
    owner_user_id: str
    source_audio_id: str | None = None
    source_filename: str | None = None
    title: str | None = None
    display_title: str
    created_at: str
    has_summary: bool = False
    has_tone_analytics: bool = False


class TranscriptSourceGroup(BaseModel):
    source_id: str | None = None
    items: list[TranscriptListItem]


class TranscriptListResponse(BaseModel):
    items: list[TranscriptListItem] = Field(default_factory=list)
    groups: list[TranscriptSourceGroup] | None = None
    total: int
    hidden_count: int


class SummaryListItem(LibraryShareFields):
    id: str
    org_id: str
    owner_user_id: str
    source_transcript_id: str | None = None
    source_transcript_title: str | None = None
    source_audio_id: str | None = None
    skill_ids: list[str] = Field(default_factory=list)
    title: str | None = None
    display_title: str
    edited: bool = False
    created_at: str


class SummarySourceGroup(BaseModel):
    source_id: str | None = None
    items: list[SummaryListItem]


class SummaryListResponse(BaseModel):
    items: list[SummaryListItem] = Field(default_factory=list)
    groups: list[SummarySourceGroup] | None = None
    total: int
    hidden_count: int


class AudioDetailResponse(LibraryShareFields):
    id: str
    org_id: str
    owner_user_id: str
    filename: str
    source_url: str | None = None
    duration_sec: float | None = None
    created_at: str
    transcripts: list[TranscriptListItem] = Field(default_factory=list)
    can_transcribe: bool = False


class TranscriptDetailResponse(TranscriptListItem):
    utterances: list[dict[str, Any]] = Field(default_factory=list)
    summaries: list[SummaryListItem] = Field(default_factory=list)
    call_summary: dict[str, Any] | None = None
    tone_layers: list[Any] | None = None


class SummaryDetailResponse(SummaryListItem):
    body: str


def _derived_audio_defaults() -> dict:
    return {
        "has_transcript": False,
        "has_summary": False,
        "transcript_id": None,
        "summary_transcript_id": None,
    }
