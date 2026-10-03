"""OAuth 2.1 JSON endpoint response models (OpenAPI; HTML flows excluded)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OAuthErrorResponse(BaseModel):
    error: str


class OAuthAuthorizationServerMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str
    jwks_uri: str
    response_types_supported: list[str]
    grant_types_supported: list[str]
    code_challenge_methods_supported: list[str]
    token_endpoint_auth_methods_supported: list[str]
    scopes_supported: list[str]


class OAuthJwksResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    keys: list[dict[str, Any]] = Field(default_factory=list)


class OAuthProtectedResourceMetadata(BaseModel):
    resource: str
    authorization_servers: list[str]
    scopes_supported: list[str]
    bearer_methods_supported: list[str]


class OAuthClientRegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_id: str
    client_name: str
    redirect_uris: list[str]
    grant_types: list[str]
    response_types: list[str]
    token_endpoint_auth_method: str
    client_id_issued_at: int
    client_secret: str | None = None


class OAuthTokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str
    scope: str
