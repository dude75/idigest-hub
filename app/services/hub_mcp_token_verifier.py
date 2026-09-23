"""Verify hub-issued OAuth JWTs for the embedded MCP resource server."""

from __future__ import annotations

from mcp.server.auth.provider import AccessToken

from app.db import SessionLocal, get_engine
from app.services.oauth_provider import mcp_resource_url as resolve_mcp_resource_url, verify_access_token
from app.services.oauth_scopes import normalize_scopes


class HubMcpTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        get_engine()
        if SessionLocal is None:
            return None
        with SessionLocal() as db:
            payload = verify_access_token(db, token)
            if payload is None:
                return None
            resource = resolve_mcp_resource_url(db=db)
            if not resource:
                return None
            scopes = sorted(normalize_scopes(payload.get("scope")))
            client_id = payload.get("azp") or payload.get("client_id") or "unknown"
            exp = payload.get("exp")
            expires_at = int(exp) if exp is not None else None
            return AccessToken(
                token=token,
                client_id=str(client_id),
                scopes=scopes,
                expires_at=expires_at,
                resource=resource,
                subject=str(payload.get("sub")) if payload.get("sub") else None,
                claims=payload,
            )
