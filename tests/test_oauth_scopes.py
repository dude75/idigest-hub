"""OAuth scope parsing helpers."""

from __future__ import annotations

from app.services.oauth_scopes import normalize_scopes, scopes_from_bearer_metadata


def test_normalize_scopes_accepts_list_claim():
    assert normalize_scopes(["audio:read", "tasks:write"]) == frozenset({"audio:read", "tasks:write"})


def test_normalize_scopes_splits_commas():
    assert normalize_scopes("audio:read,tasks:write") == frozenset({"audio:read", "tasks:write"})


def test_scopes_from_bearer_metadata_falls_back_to_claim():
    scopes = scopes_from_bearer_metadata(
        token_scopes=[],
        scope_claim="skills:read tasks:write",
    )
    assert scopes == frozenset({"skills:read", "tasks:write"})
