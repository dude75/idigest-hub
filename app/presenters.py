"""JSON-представление сущностей для API."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from app.models import (
    ApiToken,
    Audio,
    Organization,
    Skill,
    Summary,
    Tariff,
    Task,
    Transcript,
    User,
    WorkerNode,
)
from app.money import money_str
from app.services.sso import org_sso_public


def user_public(user: User, role: str | None = None) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "locale": user.locale,
        "default_route": user.default_route,
        "disabled": user.disabled_at is not None,
        "must_change_password": user.must_change_password,
        "is_instance_admin": user.is_instance_admin,
        "role": role,
        "auth_provider": user.auth_provider,
    }


def tariff_public(tariff: Tariff, org_count: int | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": tariff.id,
        "name": tariff.name,
        "unlimited": tariff.unlimited,
        "available_on_signup": tariff.available_on_signup,
        "archived": tariff.archived_at is not None,
        "price_per_audio_sec": str(tariff.price_per_audio_sec),
        "price_per_summarize_job": str(tariff.price_per_summarize_job),
        "price_per_1k_summary_chars": str(tariff.price_per_1k_summary_chars),
        "audio_retention_days": tariff.audio_retention_days,
        "api_enabled": tariff.api_enabled,
        "signup_credit": money_str(Decimal(tariff.signup_credit)),
        "max_upload_bytes": tariff.max_upload_bytes,
    }
    if org_count is not None:
        body["org_count"] = org_count
    return body


def org_public(
    org: Organization,
    *,
    usage: dict[str, Any] | None = None,
    public_base_url: str | None = None,
) -> dict[str, Any]:
    tariff = org.tariff
    body: dict[str, Any] = {
        "id": org.id,
        "name": org.name,
        "is_personal": org.is_personal,
        "password_ttl_days": org.password_ttl_days,
        "balance": money_str(Decimal(org.balance)),
        "unlimited": tariff.unlimited,
        "tariff": tariff_public(tariff),
        "sso": org_sso_public(org, public_base_url=public_base_url),
    }
    if usage is not None:
        body["usage"] = usage
    return body


def worker_public(node: WorkerNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "type": node.type,
        "name": node.name,
        "base_url": node.base_url,
        "weight": node.weight,
        "enabled": node.enabled,
        "last_health": node.last_health,
        "last_seen_version": node.last_seen_version,
        "last_health_at": node.last_health_at.isoformat() if node.last_health_at else None,
    }


def skill_public(skill: Skill, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {
        "id": skill.id,
        "scope": skill.scope,
        "org_id": skill.org_id,
        "owner_user_id": skill.owner_user_id,
        "name": skill.name,
        "body": skill.body,
        "created_at": skill.created_at.isoformat(),
        "updated_at": skill.updated_at.isoformat(),
    }
    if extra:
        body.update(extra)
    return body


def audio_public(audio: Audio, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {
        "id": audio.id,
        "org_id": audio.org_id,
        "owner_user_id": audio.owner_user_id,
        "filename": audio.original_filename,
        "duration_sec": audio.duration_sec,
        "created_at": audio.created_at.isoformat(),
    }
    if extra:
        body.update(extra)
    return body


def transcript_display_title(transcript: Transcript, *, source_filename: str | None = None) -> str:
    if transcript.title and transcript.title.strip():
        return transcript.title.strip()
    if source_filename:
        return Path(source_filename).stem
    return f"transcript-{transcript.id[:8]}"


def summary_display_title(
    summary: Summary,
    *,
    source_transcript: Transcript | None = None,
    source_filename: str | None = None,
) -> str:
    if summary.title and summary.title.strip():
        return summary.title.strip()
    if source_transcript is not None:
        tr_name = transcript_display_title(source_transcript, source_filename=source_filename)
        return f"{tr_name}-{summary.id[:8]}"
    return summary.id[:8]


def transcript_public(
    transcript: Transcript,
    utterances: list | None = None,
    extra: dict[str, Any] | None = None,
    *,
    source_filename: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": transcript.id,
        "org_id": transcript.org_id,
        "owner_user_id": transcript.owner_user_id,
        "source_audio_id": transcript.source_audio_id,
        "source_filename": source_filename,
        "title": transcript.title,
        "display_title": transcript_display_title(transcript, source_filename=source_filename),
        "created_at": transcript.created_at.isoformat(),
    }
    if utterances is not None:
        body["utterances"] = utterances
    if extra:
        body.update(extra)
    return body


def summary_public(
    summary: Summary,
    body_text: str | None = None,
    extra: dict[str, Any] | None = None,
    *,
    source_transcript: Transcript | None = None,
    source_filename: str | None = None,
) -> dict[str, Any]:
    source_transcript_title = (
        transcript_display_title(source_transcript, source_filename=source_filename)
        if source_transcript is not None
        else None
    )
    payload: dict[str, Any] = {
        "id": summary.id,
        "org_id": summary.org_id,
        "owner_user_id": summary.owner_user_id,
        "source_transcript_id": summary.source_transcript_id,
        "source_transcript_title": source_transcript_title,
        "skill_ids": summary.skill_ids_json,
        "title": summary.title,
        "display_title": summary_display_title(
            summary,
            source_transcript=source_transcript,
            source_filename=source_filename,
        ),
        "edited": summary.edited,
        "created_at": summary.created_at.isoformat(),
    }
    if body_text is not None:
        payload["body"] = body_text
    if extra:
        payload.update(extra)
    return payload


def task_public(task: Task, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "task_id": task.id,
        "type": task.type,
        "status": task.status,
        "meta": task.meta_json or {},
        "transcript_id": task.produced_transcript_id,
        "summary_id": task.produced_summary_id,
        "error": None,
        "org_id": task.org_id,
        "user_id": task.user_id,
        "audio_id": task.audio_id,
        "source_transcript_id": task.transcript_id,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }
    if task.status == "error" and task.error_code:
        body["error"] = {"code": task.error_code}
    if extra:
        body.update(extra)
    return body


def token_public(token: ApiToken, *, blocked_by_tariff: bool = False) -> dict[str, Any]:
    return {
        "id": token.id,
        "name": token.name,
        "prefix": token.prefix,
        "revoked": token.revoked_at is not None,
        "blocked_by_tariff": blocked_by_tariff and token.revoked_at is None,
        "created_at": token.created_at.isoformat(),
    }
