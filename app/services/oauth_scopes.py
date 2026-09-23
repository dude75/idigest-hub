"""OAuth scopes issued by the hub authorization server."""

from __future__ import annotations

SCOPE_TRANSCRIPTS_READ = "transcripts:read"

SUPPORTED_SCOPES: frozenset[str] = frozenset({SCOPE_TRANSCRIPTS_READ})


def normalize_scopes(raw: str | None) -> frozenset[str]:
    if not raw or not raw.strip():
        return frozenset()
    parts = {part.strip() for part in raw.split() if part.strip()}
    return frozenset(parts)


def validate_requested_scopes(requested: frozenset[str]) -> frozenset[str]:
    unknown = requested - SUPPORTED_SCOPES
    if unknown:
        raise ValueError(f"unsupported scope: {sorted(unknown)[0]}")
    if not requested:
        return frozenset({SCOPE_TRANSCRIPTS_READ})
    return requested


def scopes_to_string(scopes: frozenset[str]) -> str:
    return " ".join(sorted(scopes))
