"""OAuth scopes issued by the hub authorization server."""

from __future__ import annotations

import re
from collections.abc import Iterable

SCOPE_AUDIO_READ = "audio:read"
SCOPE_AUDIO_WRITE = "audio:write"
SCOPE_TRANSCRIPTS_READ = "transcripts:read"
SCOPE_TRANSCRIPTS_WRITE = "transcripts:write"
SCOPE_SUMMARIES_READ = "summaries:read"
SCOPE_SUMMARIES_WRITE = "summaries:write"
SCOPE_SKILLS_READ = "skills:read"
SCOPE_SKILLS_WRITE = "skills:write"
SCOPE_TASKS_WRITE = "tasks:write"

SCOPE_ORDER: tuple[str, ...] = (
    SCOPE_AUDIO_READ,
    SCOPE_AUDIO_WRITE,
    SCOPE_TRANSCRIPTS_READ,
    SCOPE_TRANSCRIPTS_WRITE,
    SCOPE_SUMMARIES_READ,
    SCOPE_SUMMARIES_WRITE,
    SCOPE_SKILLS_READ,
    SCOPE_SKILLS_WRITE,
    SCOPE_TASKS_WRITE,
)

SUPPORTED_SCOPES: frozenset[str] = frozenset(SCOPE_ORDER)


def normalize_scopes(raw: str | Iterable[str] | None) -> frozenset[str]:
    """Parse OAuth scope values from authorize params, JWT claims, or token metadata."""
    if raw is None:
        return frozenset()
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return frozenset()
        parts = {part for part in re.split(r"[\s,]+", text) if part}
        return frozenset(parts)
    scopes: set[str] = set()
    for item in raw:
        scopes.update(normalize_scopes(item))
    return frozenset(scopes)


def scopes_from_bearer_metadata(
    *,
    token_scopes: Iterable[str] | None = None,
    scope_claim: str | Iterable[str] | None = None,
) -> frozenset[str]:
    """Resolve granted scopes from MCP AccessToken fields (list + JWT claim fallback)."""
    if token_scopes is not None:
        from_list = normalize_scopes(token_scopes)
        if from_list:
            return from_list
    return normalize_scopes(scope_claim)


def validate_requested_scopes(requested: frozenset[str]) -> frozenset[str]:
    unknown = requested - SUPPORTED_SCOPES
    if unknown:
        raise ValueError(f"unsupported scope: {sorted(unknown)[0]}")
    if not requested:
        return SUPPORTED_SCOPES
    return requested


def ordered_scopes(scopes: Iterable[str]) -> list[str]:
    wanted = set(scopes)
    return [scope for scope in SCOPE_ORDER if scope in wanted]


def scope_label_key(scope: str) -> str:
    return "oauth_scope_" + scope.replace(":", "_")


def scopes_to_string(scopes: frozenset[str]) -> str:
    return " ".join(ordered_scopes(scopes))
