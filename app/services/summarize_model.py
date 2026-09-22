"""Summarize worker LLM model name from GET /health."""

from __future__ import annotations

from typing import Any

_LLM_STATUS = frozenset({"ready", "not_ready", "unavailable"})


def summarize_model_from_health(health: dict[str, Any] | None) -> str | None:
    if not health:
        return None
    for key in ("model", "llm_model"):
        raw = health.get(key)
        if isinstance(raw, str):
            name = raw.strip()
            if name:
                return name
    llm = health.get("llm")
    if isinstance(llm, str):
        name = llm.strip()
        if name and name.lower() not in _LLM_STATUS:
            return name
    return None
