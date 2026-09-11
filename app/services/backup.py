"""User data backup archive builder."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from datetime import date

from sqlalchemy.orm import Session

from app.crypto import decrypt_str
from app.deps import AuthContext
from app.models import Summary, Transcript
from app.presenters import summary_display_title, transcript_display_title
from app.services.export import safe_filename, unwrap_markdown_fence

ARCHIVE_MEDIA = {
    "zip": "application/zip",
    "tgz": "application/gzip",
}


def build_backup(
    ctx: AuthContext,
    db: Session,
    *,
    include_transcripts: bool,
    include_summaries: bool,
    include_skills: bool,
    archive_format: str,
) -> tuple[bytes, str, str]:
    org, _ = ctx.require_org()
    files: dict[str, str | bytes] = {}
    included: list[str] = []

    manifest: dict = {
        "version": 1,
        "created_at": date.today().isoformat(),
        "user_id": ctx.user.id,
        "email": ctx.user.email,
        "org_id": org.id,
        "includes": [],
    }

    if include_transcripts:
        from app.routers.library import _audio_filenames, _list_filter

        rows = _list_filter(ctx, db, Transcript, "transcript", include_hidden=True)
        filenames = _audio_filenames(db, {row.source_audio_id for row in rows})
        for row in rows:
            utterances = json.loads(decrypt_str(row.utterances_encrypted))
            source_filename = filenames.get(row.source_audio_id) if row.source_audio_id else None
            display = transcript_display_title(row, source_filename=source_filename)
            stem = safe_filename(f"{row.id}_{display}")
            payload = {
                "id": row.id,
                "title": row.title,
                "display_title": display,
                "created_at": row.created_at.isoformat(),
                "source_audio_id": row.source_audio_id,
                "utterances": utterances,
            }
            files[f"transcripts/{stem}.json"] = json.dumps(payload, ensure_ascii=False, indent=2)
        included.append("transcripts")
        manifest["transcript_count"] = len(rows)

    if include_summaries:
        from app.routers.library import (
            _audio_filenames,
            _list_filter,
            _summary_source_context,
            _transcripts_by_id,
        )

        rows = _list_filter(ctx, db, Summary, "summary", include_hidden=True)
        transcripts = _transcripts_by_id(db, {row.source_transcript_id for row in rows})
        audio_filenames = _audio_filenames(
            db, {tr.source_audio_id for tr in transcripts.values() if tr.source_audio_id}
        )
        for row in rows:
            body = unwrap_markdown_fence(decrypt_str(row.body_encrypted))
            source_transcript, source_filename = _summary_source_context(row, transcripts, audio_filenames)
            display = summary_display_title(
                row,
                source_transcript=source_transcript,
                source_filename=source_filename,
            )
            stem = safe_filename(f"{row.id}_{display}")
            files[f"summaries/{stem}.md"] = body
            meta = {
                "id": row.id,
                "title": row.title,
                "display_title": display,
                "created_at": row.created_at.isoformat(),
                "source_transcript_id": row.source_transcript_id,
                "skill_ids": row.skill_ids_json or [],
                "edited": row.edited,
            }
            files[f"summaries/{stem}.meta.json"] = json.dumps(meta, ensure_ascii=False, indent=2)
        included.append("summaries")
        manifest["summary_count"] = len(rows)

    if include_skills:
        from app.routers.skills import _visible_skills

        items = [
            (skill, extra)
            for skill, extra in _visible_skills(db, ctx, scope=None)
            if extra.get("catalog") in {"self", "shared"}
        ]
        for skill, extra in items:
            stem = safe_filename(f"{skill.id}_{skill.name}")
            files[f"skills/{stem}.md"] = skill.body
            meta = {
                "id": skill.id,
                "name": skill.name,
                "scope": skill.scope,
                "created_at": skill.created_at.isoformat(),
                "updated_at": skill.updated_at.isoformat(),
                "catalog": extra.get("catalog"),
            }
            files[f"skills/{stem}.meta.json"] = json.dumps(meta, ensure_ascii=False, indent=2)
        included.append("skills")
        manifest["skill_count"] = len(items)

    manifest["includes"] = included
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2)

    ext = "zip" if archive_format == "zip" else "tar.gz"
    filename = safe_filename(f"idigest-backup-{date.today().isoformat()}.{ext}")
    return _pack(files, archive_format), filename, ARCHIVE_MEDIA[archive_format]


def _pack(files: dict[str, str | bytes], archive_format: str) -> bytes:
    buf = io.BytesIO()
    if archive_format == "zip":
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in sorted(files.items()):
                if isinstance(data, str):
                    data = data.encode("utf-8")
                zf.writestr(name, data)
    else:
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for name, data in sorted(files.items()):
                if isinstance(data, str):
                    data = data.encode("utf-8")
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()
