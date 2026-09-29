"""Restore profile backup archives (inverse of app.services.backup)."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.constants import MAX_UPLOAD_BYTES_CAP
from app.crypto import encrypt_str
from app.deps import AuthContext
from app.errors import ErrorCode
from app.models import Audio, Skill, Summary, Transcript, new_id
from app.timeutil import utcnow


@dataclass
class _Counters:
    created: int = 0
    updated: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"created": self.created, "updated": self.updated, "skipped": self.skipped}


@dataclass
class RestoreReport:
    mode: str
    skills: _Counters = field(default_factory=_Counters)
    transcripts: _Counters = field(default_factory=_Counters)
    summaries: _Counters = field(default_factory=_Counters)

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "skills": self.skills.as_dict(),
            "transcripts": self.transcripts.as_dict(),
            "summaries": self.summaries.as_dict(),
        }


def restore_backup(
    ctx: AuthContext,
    db: Session,
    raw: bytes,
    *,
    filename: str | None = None,
) -> RestoreReport:
    if len(raw) > MAX_UPLOAD_BYTES_CAP:
        ctx.raise_error(ErrorCode.payload_too_large)
    org, _ = ctx.require_org()
    files = _unpack(raw, filename)
    manifest = _load_manifest(ctx, files)
    same_context = manifest.get("user_id") == ctx.user.id and manifest.get("org_id") == org.id
    mode = "restore" if same_context else "import"
    report = RestoreReport(mode=mode)

    skill_map: dict[str, str] = {}
    if "skills" in (manifest.get("includes") or []):
        _restore_skills(ctx, db, files, same_context, report.skills, skill_map)
        db.flush()

    transcript_map: dict[str, str] = {}
    if "transcripts" in (manifest.get("includes") or []):
        _restore_transcripts(ctx, db, org.id, files, same_context, report.transcripts, transcript_map)
        db.flush()

    if "summaries" in (manifest.get("includes") or []):
        _restore_summaries(
            ctx,
            db,
            org.id,
            files,
            same_context,
            report.summaries,
            transcript_map,
            skill_map,
        )

    return report


def _unpack(raw: bytes, filename: str | None) -> dict[str, bytes]:
    name = (filename or "").lower()
    if name.endswith(".tar.gz") or name.endswith(".tgz") or raw[:2] == b"\x1f\x8b":
        return _unpack_tgz(raw)
    return _unpack_zip(raw)


def _unpack_zip(raw: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                out[info.filename.replace("\\", "/")] = zf.read(info.filename)
    except zipfile.BadZipFile:
        return _unpack_tgz(raw)
    return out


def _unpack_tgz(raw: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            out[member.name.replace("\\", "/")] = extracted.read()
    return out


def _load_manifest(ctx: AuthContext, files: dict[str, bytes]) -> dict[str, Any]:
    raw = files.get("manifest.json")
    if raw is None:
        ctx.raise_error(ErrorCode.validation_error)
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        ctx.raise_error(ErrorCode.validation_error)
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        ctx.raise_error(ErrorCode.validation_error)
    return manifest


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return utcnow()
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return utcnow()


def _transcript_blob(data: dict[str, Any]) -> str:
    if isinstance(data.get("worker_response"), dict):
        stored: Any = data["worker_response"]
    elif "utterances" in data:
        stored = data["utterances"]
    else:
        stored = []
    return json.dumps(stored, ensure_ascii=False)


def _valid_audio(db: Session, org_id: str, user_id: str, audio_id: str | None) -> str | None:
    if not audio_id:
        return None
    audio = db.get(Audio, audio_id)
    if audio is None or audio.org_id != org_id or audio.owner_user_id != user_id:
        return None
    return audio_id


def _resolve_transcript_id(
    db: Session,
    org_id: str,
    user_id: str,
    source_id: str | None,
    transcript_map: dict[str, str],
    *,
    same_context: bool,
) -> str | None:
    if not source_id:
        return None
    if same_context:
        row = db.get(Transcript, source_id)
        if row is not None and row.org_id == org_id and row.owner_user_id == user_id:
            return source_id
        mapped = transcript_map.get(source_id)
        if mapped:
            return mapped
        return None
    return transcript_map.get(source_id)


def _resolve_skill_ids(
    db: Session,
    user_id: str,
    skill_ids: list[Any],
    skill_map: dict[str, str],
    *,
    same_context: bool,
) -> list[str]:
    resolved: list[str] = []
    for raw in skill_ids:
        if not isinstance(raw, str):
            continue
        if same_context:
            skill = db.get(Skill, raw)
            if skill is not None and skill.scope == "self" and skill.owner_user_id == user_id:
                resolved.append(raw)
                continue
            if raw in skill_map:
                resolved.append(skill_map[raw])
        elif raw in skill_map:
            resolved.append(skill_map[raw])
    return resolved


def _restore_skills(
    ctx: AuthContext,
    db: Session,
    files: dict[str, bytes],
    same_context: bool,
    counters: _Counters,
    skill_map: dict[str, str],
) -> None:
    org, _ = ctx.require_org()
    for path, raw_meta in files.items():
        if not path.startswith("skills/") or not path.endswith(".meta.json"):
            continue
        stem = path[: -len(".meta.json")]
        md_path = f"{stem}.md"
        body_raw = files.get(md_path)
        if body_raw is None:
            counters.skipped += 1
            continue
        try:
            meta = json.loads(raw_meta.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            counters.skipped += 1
            continue
        if not isinstance(meta, dict) or not meta.get("id"):
            counters.skipped += 1
            continue
        old_id = str(meta["id"])
        catalog = meta.get("catalog")
        if same_context and catalog == "shared":
            counters.skipped += 1
            continue
        body = body_raw.decode("utf-8")
        name = str(meta.get("name") or "Skill").strip() or "Skill"
        created_at = _parse_dt(meta.get("created_at") if isinstance(meta.get("created_at"), str) else None)
        updated_at = _parse_dt(meta.get("updated_at") if isinstance(meta.get("updated_at"), str) else None)

        if same_context:
            row = db.get(Skill, old_id)
            if row is not None:
                if row.scope != "self" or row.owner_user_id != ctx.user.id:
                    counters.skipped += 1
                    continue
                row.name = name
                row.body = body
                row.updated_at = updated_at
                skill_map[old_id] = old_id
                counters.updated += 1
                continue
            skill = Skill(
                id=old_id,
                scope="self",
                org_id=org.id,
                owner_user_id=ctx.user.id,
                name=name,
                body=body,
                created_at=created_at,
                updated_at=updated_at,
            )
            db.add(skill)
            skill_map[old_id] = old_id
            counters.created += 1
        else:
            new_id_val = new_id()
            skill = Skill(
                id=new_id_val,
                scope="self",
                org_id=org.id,
                owner_user_id=ctx.user.id,
                name=name,
                body=body,
                created_at=created_at,
                updated_at=updated_at,
            )
            db.add(skill)
            skill_map[old_id] = new_id_val
            counters.created += 1


def _restore_transcripts(
    ctx: AuthContext,
    db: Session,
    org_id: str,
    files: dict[str, bytes],
    same_context: bool,
    counters: _Counters,
    transcript_map: dict[str, str],
) -> None:
    for path, raw in files.items():
        if not path.startswith("transcripts/") or not path.endswith(".json"):
            continue
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            counters.skipped += 1
            continue
        if not isinstance(data, dict) or not data.get("id"):
            counters.skipped += 1
            continue
        old_id = str(data["id"])
        encrypted = encrypt_str(_transcript_blob(data), db)
        title = data.get("title")
        if isinstance(title, str):
            title = title.strip() or None
        else:
            title = None
        created_at = _parse_dt(data.get("created_at") if isinstance(data.get("created_at"), str) else None)
        source_audio_id = _valid_audio(
            db,
            org_id,
            ctx.user.id,
            data.get("source_audio_id") if isinstance(data.get("source_audio_id"), str) else None,
        )

        if same_context:
            row = db.get(Transcript, old_id)
            if row is not None:
                if row.org_id != org_id or row.owner_user_id != ctx.user.id:
                    counters.skipped += 1
                    continue
                row.title = title
                row.utterances_encrypted = encrypted
                row.source_audio_id = source_audio_id
                transcript_map[old_id] = old_id
                counters.updated += 1
                continue
            row = Transcript(
                id=old_id,
                org_id=org_id,
                owner_user_id=ctx.user.id,
                source_audio_id=source_audio_id,
                title=title,
                utterances_encrypted=encrypted,
                created_at=created_at,
            )
            db.add(row)
            transcript_map[old_id] = old_id
            counters.created += 1
        else:
            new_id_val = new_id()
            row = Transcript(
                id=new_id_val,
                org_id=org_id,
                owner_user_id=ctx.user.id,
                source_audio_id=None,
                title=title,
                utterances_encrypted=encrypted,
                created_at=created_at,
            )
            db.add(row)
            transcript_map[old_id] = new_id_val
            counters.created += 1


def _restore_summaries(
    ctx: AuthContext,
    db: Session,
    org_id: str,
    files: dict[str, bytes],
    same_context: bool,
    counters: _Counters,
    transcript_map: dict[str, str],
    skill_map: dict[str, str],
) -> None:
    for path, raw_meta in files.items():
        if not path.startswith("summaries/") or not path.endswith(".meta.json"):
            continue
        stem = path[: -len(".meta.json")]
        md_path = f"{stem}.md"
        body_raw = files.get(md_path)
        if body_raw is None:
            counters.skipped += 1
            continue
        try:
            meta = json.loads(raw_meta.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            counters.skipped += 1
            continue
        if not isinstance(meta, dict) or not meta.get("id"):
            counters.skipped += 1
            continue
        old_id = str(meta["id"])
        body = body_raw.decode("utf-8")
        title = meta.get("title")
        if isinstance(title, str):
            title = title.strip() or None
        else:
            title = None
        edited = bool(meta.get("edited"))
        created_at = _parse_dt(meta.get("created_at") if isinstance(meta.get("created_at"), str) else None)
        raw_source = meta.get("source_transcript_id")
        source_transcript_id = _resolve_transcript_id(
            db,
            org_id,
            ctx.user.id,
            raw_source if isinstance(raw_source, str) else None,
            transcript_map,
            same_context=same_context,
        )
        skill_ids = _resolve_skill_ids(
            db,
            ctx.user.id,
            meta.get("skill_ids") if isinstance(meta.get("skill_ids"), list) else [],
            skill_map,
            same_context=same_context,
        )
        if not same_context and source_transcript_id is not None:
            allowed = set(transcript_map.values())
            if source_transcript_id not in allowed:
                source_transcript_id = None
        encrypted = encrypt_str(body, db)

        if same_context:
            row = db.get(Summary, old_id)
            if row is not None:
                if row.org_id != org_id or row.owner_user_id != ctx.user.id:
                    counters.skipped += 1
                    continue
                row.title = title
                row.body_encrypted = encrypted
                row.source_transcript_id = source_transcript_id
                row.skill_ids_json = skill_ids
                row.edited = edited
                counters.updated += 1
                continue
            row = Summary(
                id=old_id,
                org_id=org_id,
                owner_user_id=ctx.user.id,
                source_transcript_id=source_transcript_id,
                skill_ids_json=skill_ids,
                title=title,
                body_encrypted=encrypted,
                edited=edited,
                created_at=created_at,
            )
            db.add(row)
            counters.created += 1
        else:
            row = Summary(
                id=new_id(),
                org_id=org_id,
                owner_user_id=ctx.user.id,
                source_transcript_id=source_transcript_id,
                skill_ids_json=skill_ids,
                title=title,
                body_encrypted=encrypted,
                edited=edited,
                created_at=created_at,
            )
            db.add(row)
            counters.created += 1
