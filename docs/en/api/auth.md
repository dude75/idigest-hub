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

Success: `{ "status": "ok" }` + cookie. Errors: `invalid_credentials`, `sso_login_required` (403) when org SSO is enabled and the user is `org_member`.

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

## Current user

### GET `/me`

```json
{
  "user": {
    "id", "email", "locale", "default_route",
    "disabled", "must_change_password", "is_instance_admin", "role"
  },
  "org": { ... } | null,
  "impersonating": false,
  "actor": { ... } | null,
  "must_change_password": false
}
```

`role`: `instance_admin` | `org_admin` | `org_member` | null

### PATCH `/me`

```json
{
  "locale": "es",
  "default_route": "tasks"
}
```

`default_route` must be allowed for role. Error: `validation_error`.

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

```json
{ "name": "CI pipeline" }
```

Response includes one-time `"token": "idg_..."` field.

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

- [Security](../architecture/security.md)
- [Roles](../domain/roles-and-access.md)
