# Auth API

Prefix: `/api/v1`

## Bootstrap

### GET `/setup/status`

Public. `{ "bootstrap_done": true|false }`

### POST `/setup`

One-time instance admin creation.

```json
{
  "email": "admin@example.com",
  "password": "minimum-8-chars",
  "bootstrap_token": "<INSTANCE_BOOTSTRAP_TOKEN>",
  "locale": "en"
}
```

Success: sets session cookie, returns `{ "status": "ok", "user": {...} }`.

Errors: `bootstrap_invalid` (401), `setup_already_done` (409), `email_taken` (409), `rate_limited` (429).

## Signup & login

### GET `/auth/signup-tariffs`

Public (after bootstrap). Lists tariffs with `available_on_signup` and not archived. Empty if signup disabled.

### POST `/auth/signup`

```json
{
  "email": "user@example.com",
  "password": "minimum-8-chars",
  "tariff_id": "uuid",
  "locale": "ru"
}
```

Creates user + org + session. Errors: `signup_disabled`, `tariff_not_available`, `email_taken`.

### POST `/auth/login`

```json
{ "email": "...", "password": "..." }
```

Success (no 2FA): `{ "status": "ok" }` + session cookie.

When the user has TOTP 2FA enabled (local auth only): `{ "status": "mfa_required", "challenge_id": "..." }` — no cookie yet. Complete login via [MFA verify](#post-authmfaverify) or [MFA recover](#post-authmfarecover). Challenge TTL: 5 minutes.

Errors: `invalid_credentials`, `sso_login_required` (403) when org SSO is enabled and the user is `org_member`.

### POST `/auth/logout`

Optional auth. Clears session.

## SSO (OIDC, Keycloak-compatible)

Per-organization. Requires instance **Public URL** (`public_base_url` in Instance → Settings). Browser entry: `{public_url}/sso/{org_id}`.

### GET `/auth/sso/{org_id}/info`

Public. `{ "org_id", "org_name", "configured", "enabled", "login_url" }`.

### GET `/auth/sso/{org_id}/start`

Public. Redirects (302) to the IdP authorization URL. Errors: `sso_disabled` (403), `sso_misconfigured` (400).

### GET `/auth/sso/{org_id}/callback`

OAuth callback (`code`, `state` query params). On success: sets session cookie, redirects to `{public_base_url}/app`. Errors: `sso_disabled`, `sso_misconfigured`, `sso_state_invalid`, `sso_email_missing`, `sso_user_wrong_org`.

Auto-provision: first SSO login for an unknown email creates `org_member` in that org (email from IdP claims). Existing users must belong to the same org.

**Password login when SSO is configured:** `org_admin` only (break-glass). `org_member` must use SSO once enabled.

Org admin configures credentials via [Org SSO endpoints](org.md#sso).

## OAuth 2.1 provider (MCP / Open WebUI)

Optional (`OAUTH_PROVIDER_ENABLED=true` in `.env`). Hub acts as an **Authorization Server** and hosts **MCP** at `/mcp` (Streamable HTTP). Requires **Public URL**; default resource URI is `{public_url}/mcp` (override with `OAUTH_MCP_RESOURCE_URL`).

Discovery: `GET /.well-known/oauth-authorization-server`, `GET /.well-known/jwks.json`. DCR: `POST /oauth/register`. Authorization Code + **PKCE S256**: `GET /oauth/authorize`, `POST /oauth/token`.

JWT access tokens work as `Authorization: Bearer` alongside PAT (`idg_…`) on **REST** `/api/v1`.

**OAuth scopes** (space-separated on authorize; listed in `GET /.well-known/oauth-protected-resource/mcp`):

| Scope | REST (JWT) | MCP |
| ----- | ---------- | --- |
| `audio:read` | — | `list_audios`, `get_audio` |
| `audio:write` | — | `create_audio_upload`, `delete_audio` |
| `transcripts:read` | `GET /transcripts`, `GET /transcripts/{id}` | `list_transcripts`, `get_transcript` |
| `transcripts:write` | — | `update_transcript`, `delete_transcript` |
| `summaries:read` | — | `list_summaries`, `get_summary` |
| `summaries:write` | — | `update_summary`, `delete_summary` |
| `skills:read` | — | `list_skills`, `get_skill` |
| `skills:write` | — | `create_skill`, `update_skill`, `delete_skill` |
| `tasks:write` | — | `create_audio_import`, `create_summary`, `get_task`, `stop_capture_task` |

If the client omits `scope`, the hub grants every supported scope. Full tool reference: **[mcp.md](mcp.md)**.

**MCP / OAuth authorize** — only users with org membership and role `org_admin` or `org_member`, plus tariff `api_enabled` and no account blocks. **Instance admins without org** cannot complete OAuth (instance admins may still use PAT without org separately).

Browser authorize/consent uses styled HTML pages (login, consent, blocked-account errors). `/oauth/token` and `/oauth/register` stay JSON.

## Password

### POST `/auth/password/change`

Auth required. Not allowed while impersonating.

```json
{
  "current_password": "...",
  "new_password": "minimum-8-chars"
}
```

`current_password` optional when `must_change_password` is true.

Revokes all other browser sessions and API tokens for the user, then issues a new session cookie for the current client.

### POST `/auth/password/reset/request`

```json
{ "email": "..." }
```

Always returns `{ "status": "ok" }` (no email enumeration). Sends mail if user exists, SMTP is configured, and **Public URL** is set. Error if SMTP or Public URL missing: `recovery_disabled`. Skips mail silently for users who must use SSO (`org_member` with SSO enabled).

### POST `/auth/password/reset/confirm`

```json
{
  "token": "from-email-link",
  "new_password": "minimum-8-chars"
}
```

Invalid/expired token → `not_found`.

Revokes all browser sessions and API tokens for the user. No new session is created — log in again after reset.

## Two-factor authentication (TOTP)

Local users (`auth_provider=local`) only. SSO users rely on IdP MFA — Hub 2FA is not applied.

### POST `/auth/mfa/verify`

Public (no session). Complete login after `mfa_required`:

```json
{ "challenge_id": "...", "code": "123456" }
```

Success: `{ "status": "ok" }` + session cookie. Errors: `mfa_challenge_invalid` (401), `invalid_totp` (401), `rate_limited` (429).

### POST `/auth/mfa/recover`

Public. Same flow with a one-time recovery code instead of TOTP:

```json
{ "challenge_id": "...", "recovery_code": "..." }
```

Success: `{ "status": "ok" }` + session cookie. Consumes the recovery code. Same errors as verify.

### GET `/auth/mfa/status`

Auth required. `{ "enabled": bool, "required": bool, "enrollment_required": bool }`.

- `required` — org policy `mfa_required` applies to this user (SSO off, local auth).
- `enrollment_required` — policy requires 2FA but user has not enrolled yet; most endpoints return `mfa_enrollment_required` (403) until setup is confirmed.

### POST `/auth/mfa/setup/start`

Auth required. Not allowed while impersonating or for SSO users.

Returns `{ "secret": "...", "otpauth_uri": "otpauth://..." }` for authenticator app setup. Secret is stored pending confirmation.

### POST `/auth/mfa/setup/confirm`

Auth required.

```json
{ "code": "123456" }
```

Verifies the pending secret and enables 2FA. Response: `{ "status": "ok", "recovery_codes": ["...", ...] }` (8 one-time codes). Error: `invalid_totp`.

### POST `/auth/mfa/disable`

Auth required. User-initiated disable.

```json
{ "password": "...", "code": "123456" }
```

`code` may be a TOTP code or recovery code. Blocked when org policy requires 2FA (`forbidden`). On success revokes all sessions and API tokens. Errors: `invalid_credentials`, `invalid_totp`.

Admin reset (clears 2FA without user code): [Org reset-MFA](org.md#post-orgusersuser_idreset-mfa), [Instance reset-MFA](instance.md#post-orgsorg_idusersuser_idreset-mfa).

## Current user

### GET `/me`

```json
{
  "user": {
    "id", "email", "locale", "default_route",
    "date_time_format", "timezone",
    "asr_model", "diarization_model", "summarize_model",
    "disabled", "must_change_password", "is_instance_admin", "role"
  },
  "org": { ... } | null,
  "impersonating": false,
  "actor": { ... } | null,
  "date_time_prefs": { ... },
  "transcribe_prefs": {
    "asr_model", "diarization_model",
    "asr_source", "diarization_source",
    "instance_asr_model", "instance_diarization_model"
  },
  "transcribe_models": { "asr_models": [], "diarization_models": [] },
  "summarize_prefs": {
    "summarize_model", "source", "instance_summarize_model"
  },
  "summarize_models": { "summarize_models": [] },
  "must_change_password": false,
  "mfa_enabled": false,
  "mfa_required": false,
  "mfa_enrollment_required": false
}
```

`role`: `instance_admin` | `org_admin` | `org_member` | null

When `mfa_enrollment_required` is true, only password change, MFA setup, `/me`, and logout are allowed until 2FA is enrolled.

### PATCH `/me`

```json
{
  "locale": "es",
  "default_route": "tasks",
  "date_time_format": "us_12h",
  "timezone": "GMT+3",
  "asr_model": "parakeet",
  "diarization_model": "",
  "summarize_model": "llm-b"
}
```

`default_route` must be allowed for role. Error: `validation_error`.

`date_time_format`: `eu_24h` | `us_12h` | `iso` | `relative`, or `null` to inherit instance default.

`timezone`: `GMT-12` … `GMT+14`, or `null` to inherit instance default. Resolved values are returned on GET `/me`.

`asr_model`: model id from `transcribe_models.asr_models`, or `null` to inherit instance default.

`diarization_model`: model id from `transcribe_models.diarization_models`, `null` to inherit instance default, or `""` to disable diarization for your tasks.

`summarize_model`: name from `summarize_models.summarize_models`, or `null` to inherit the instance default. Resolved value is in `summarize_prefs` (`source`: `user` or `instance`). Unknown name → `validation_error`.

## Profile backup

### GET `/me/backup`

Auth required. Downloads a ZIP or TGZ archive of owned library data.

Query (at least one flag must be `true`):

| Param | Description |
| ----- | ----------- |
| `transcripts` | Include owned transcripts as JSON |
| `summaries` | Include owned summaries as JSON |
| `skills` | Include owned personal skills as JSON |
| `format` | `zip` (default) or `tgz` |

Response: `Content-Disposition: attachment` with manifest + selected files.

## API tokens

Require auth + org tariff `api_enabled` + no password lock.

### POST `/auth/tokens`

Cookie session only (not via Bearer). Blocked during MFA enrollment (`mfa_enrollment_required`).

```json
{ "name": "CI pipeline", "totp_code": "123456" }
```

`totp_code` required when the user has 2FA enabled (`mfa_step_up_required` if omitted). Response includes one-time `"token": "idg_..."` field.

### GET `/auth/tokens`

List tokens (prefix only). `blocked_by_tariff` if API disabled.

### DELETE `/auth/tokens/{token_id}`

Revoke token.

## Usage with Bearer token

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8080/api/v1/tasks
```

Subject to rate limits (Instance → Settings).

## Related pages

- [MCP tools](mcp.md)
- [Security](../architecture/security.md)
- [Roles](../domain/roles-and-access.md)
