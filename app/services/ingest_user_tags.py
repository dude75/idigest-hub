"""Optional user tags on import/capture tasks (applied when audio is created)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.errors import ApiError, ErrorCode
from app.models import Task
from app.services.user_tags import MAX_TAGS_PER_OBJECT, append_object_tags, normalize_tag_name, tag_name_key


def parse_ingest_user_tag_names(raw: list[str] | None) -> list[str]:
    """Deduped tag names from the client; source/platform tags are applied separately."""
    if not raw:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        name = normalize_tag_name(item)
        key = tag_name_key(name)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(name)
    # Reserve one slot for the automatic source tag (youtube, jitsi, upload, …).
    if len(cleaned) > MAX_TAGS_PER_OBJECT - 1:
        raise ApiError(ErrorCode.user_tag_limit_per_object)
    return cleaned


def merge_ingest_user_tags(meta: dict, tag_names: list[str]) -> None:
    if tag_names:
        meta["user_tags"] = tag_names


def apply_ingest_task_user_tags(db: Session, task: Task, audio_id: str) -> None:
    meta = task.meta_json if isinstance(task.meta_json, dict) else {}
    raw = meta.get("user_tags")
    if not isinstance(raw, list):
        return
    names = [item for item in raw if isinstance(item, str)]
    if not names:
        return
    try:
        tag_names = parse_ingest_user_tag_names(names)
    except ApiError:
        return
    if tag_names:
        append_object_tags(
            db,
            user_id=task.user_id,
            object_type="audio",
            object_id=audio_id,
            tag_names=tag_names,
        )
