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

org_admin. `{ "password_ttl_days": 90 }` — `0` disables TTL.

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

Sets random password, `must_change_password=true`, revokes sessions/tokens.

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
