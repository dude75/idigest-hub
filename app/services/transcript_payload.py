"""Helpers for transcript blobs stored in transcripts.utterances_encrypted."""

from __future__ import annotations

import json
from typing import Any


def build_worker_payload(body: dict[str, Any], utterances: list[dict[str, Any]]) -> dict[str, Any]:
    """Normalize a successful transcribe worker body for persistence."""
    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    return {
        "status": body.get("status") or "success",
        "meta": meta,
        "transcript": utterances,
        "error": body.get("error"),
    }


def decode_transcript_payload(raw: str) -> Any:
    return json.loads(raw)


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def normalize_utterances(utterances: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in utterances:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        for key in ("start", "end"):
            coerced = _coerce_float(row.get(key))
            if coerced is not None:
                row[key] = coerced
            elif key in row:
                row.pop(key, None)
        normalized.append(row)
    return normalized


def extract_utterances(payload: Any) -> list[dict[str, Any]]:
    """Return utterance list from stored worker response or legacy array."""
    if isinstance(payload, list):
        return normalize_utterances(payload)
    if isinstance(payload, dict):
        transcript = payload.get("transcript")
        if isinstance(transcript, list):
            return normalize_utterances(transcript)
    return []


def is_worker_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("transcript"), list)


def summarize_input_text(payload: Any) -> str:
    """JSON string sent to isummarize-worker as `text`."""
    return json.dumps(payload, ensure_ascii=False)


def export_json_payload(payload: Any) -> Any:
    """Object serialized for transcript JSON download."""
    return payload
