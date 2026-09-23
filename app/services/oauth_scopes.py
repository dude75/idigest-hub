"""OAuth scopes issued by the hub authorization server."""

from __future__ import annotations

SCOPE_TRANSCRIPTS_READ = "transcripts:read"
SCOPE_SUMMARIES_READ = "summaries:read"
SCOPE_SUMMARIES_WRITE = "summaries:write"
SCOPE_SKILLS_READ = "skills:read"
SCOPE_SKILLS_WRITE = "skills:write"
SCOPE_TASKS_WRITE = "tasks:write"

SUPPORTED_SCOPES: frozenset[str] = frozenset(
    {
        SCOPE_TRANSCRIPTS_READ,
        SCOPE_SUMMARIES_READ,
        SCOPE_SUMMARIES_WRITE,
        SCOPE_SKILLS_READ,
        SCOPE_SKILLS_WRITE,
        SCOPE_TASKS_WRITE,
    }
)


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
