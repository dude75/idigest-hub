# Organization API

Auth required. Most routes require org membership; admin routes require `org_admin`.

## Org profile

### GET `/org`

Current org + tariff + usage total.

### PATCH `/org`

org_admin. `{ "name": "Team Name" }`

### GET `/org/available-tariffs`

Tariffs available for self-service switch (non-archived, `available_on_signup`).

### PATCH `/org/tariff`

org_admin. `{ "tariff_id": "uuid" }`

### PATCH `/org/settings`

org_admin.

```json
{
  "password_ttl_days": 90,
  "mfa_required": true,
  "allow_public_links": true
}
```

`password_ttl_days`: `0` disables TTL.

`mfa_required`: when `true`, all local-auth users in the org must enroll TOTP 2FA before using the app. Mutually exclusive with SSO — cannot enable while `sso_enabled`; enabling SSO clears `mfa_required`. SSO users are not subject to Hub 2FA.

`allow_public_links`: when `false`, members cannot create public summary links and existing guest URLs return `not_found`.

## Public summary links

Org members manage links from **Public links** in the nav (or summary share dialog).

### GET `/org/public-links`

Lists active and revoked links in the org. **org_member** sees only own summaries; **org_admin** sees all.

Each item: `id`, `summary_id`, `summary_title`, `url`, `expires_at`, `pin_required`, `owner_email`, `active`, `created_at`, `revoked`.

### DELETE `/org/public-links/{link_id}`

Revoke by link id. Owner may revoke own links; org_admin may revoke any org link.

## SSO

org_admin. Keycloak-compatible OIDC per organization. Requires instance **Public URL**.

### GET `/org/sso`

Returns admin view: `issuer`, `client_id`, `has_client_secret`, `enabled`, `configured`, `public_base_url_set`, `login_url`, `callback_url` (redirect URI for Keycloak **Valid redirect URIs**).

### PATCH `/org/sso`

```json
{
  "issuer": "https://keycloak.example.com/realms/myrealm",
  "client_id": "idigest-hub",
  "client_secret": "optional-on-update",
  "clear_client_secret": false,
  "enabled": true
}
```

Omit `client_secret` to keep the stored secret. Set `clear_client_secret: true` to remove it.

Errors: `sso_misconfigured` when enabling without valid issuer/client, client secret, or Public URL.

Member login URL: `{public_url}/sso/{org_id}` (also in GET response when Public URL is set).

## Meeting capture (Jitsi hosts)

org_admin. Requires instance capture enabled with `jitsi` in allowed connectors.

### GET `/org/capture/jitsi`

```json
{
  "allowed": true,
  "bot_display_name": "Org bot default",
  "items": [
    {
      "id": "uuid",
      "host": "meet.example.com",
      "jwt_app_id": "optional",
      "jwt_secret_configured": true
    }
  ],
  "workers": [{ "id": "uuid", "name": "Capture node 1" }]
}
```

`workers` lists enabled capture nodes (informational — hosts are **not** bound to a worker id). JWT secret is write-only on update.

### PUT `/org/capture/jitsi`

Replace host list and optionally org default bot name:

```json
{
  "bot_display_name": "Team recorder",
  "items": [
    { "host": "meet.example.com", "jwt_app_id": "myapp", "jwt_secret": "…" },
    { "id": "existing-uuid", "host": "jitsi.internal", "clear_jwt_secret": true }
  ]
}
```

Errors: `capture_disabled`, `validation_error`.

## Statistics

### GET `/org/stats`

org_admin. Query:

| Param | Description |
| ----- | ----------- |
| `from` | Start date `YYYY-MM-DD` |
| `to` | End date inclusive |
| `user_id` | Filter by member |
| `kind` | `transcribe` or `summarize` |

Returns daily breakdown and totals from `usage_events`.

## Users

### GET `/org/users`

List members with roles.

### POST `/org/users`

org_admin. Create member:

```json
{
  "email": "new@example.com",
  "password": "minimum-8",
  "role": "org_member",
  "locale": "en"
}
```

### PATCH `/org/users/{user_id}`

Change role (`org_admin` | `org_member`).

### POST `/org/users/{user_id}/disable`

### POST `/org/users/{user_id}/enable`

### POST `/org/users/{user_id}/reset-password`

Generates a random password, sets `must_change_password=true`, revokes sessions/tokens.

Returns `{ "status": "ok", "password": "..." }` — show once to the admin (UI modal).

### POST `/org/users/{user_id}/reset-mfa`

org_admin. Clears TOTP enrollment and recovery codes for a local-auth member who has 2FA configured. Revokes sessions and API tokens. No-op error if 2FA not configured. SSO users: `forbidden`.

### POST `/org/users/{user_id}/offboard`

```json
{
  "action": "transfer|wipe",
  "target_user_id": "uuid"
}
```

`target_user_id` required for `transfer`.

## Related pages

- [Organizations domain](../domain/organizations.md)
- [Roles](../domain/roles-and-access.md)
