"""Auto user-tags for library ingest source.

Tag names are lowercase slugs. Keep in sync with web/src/constants/userTags.ts.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.user_tags import append_object_tags

# Keep in sync with web/src/constants/userTags.ts
UPLOAD_TAG = "upload"
MIC_RECORDING_TAG = "mic"


def import_source_tag(extractor_key: str | None) -> str | None:
    key = (extractor_key or "").strip()
    if not key:
        return None
    return key.casefold()


def capture_source_tag(connector: str | None) -> str:
    key = (connector or "jitsi").strip()
    return key.casefold()


def _apply(db: Session, *, user_id: str, audio_id: str, tag_name: str | None) -> None:
    if not tag_name:
        return
    append_object_tags(
        db,
        user_id=user_id,
        object_type="audio",
        object_id=audio_id,
        tag_names=[tag_name],
    )


def tag_audio_file_upload(db: Session, *, user_id: str, audio_id: str, from_microphone: bool) -> None:
    _apply(
        db,
        user_id=user_id,
        audio_id=audio_id,
        tag_name=MIC_RECORDING_TAG if from_microphone else UPLOAD_TAG,
    )


def tag_audio_url_import(db: Session, *, user_id: str, audio_id: str, extractor_key: str | None) -> None:
    _apply(db, user_id=user_id, audio_id=audio_id, tag_name=import_source_tag(extractor_key))


def tag_audio_capture(db: Session, *, user_id: str, audio_id: str, connector: str | None) -> None:
    _apply(db, user_id=user_id, audio_id=audio_id, tag_name=capture_source_tag(connector))
