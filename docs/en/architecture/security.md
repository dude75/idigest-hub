# Security

## Threat model (practical)

The hub is designed for **on-premise / private network** deployment:

- Operators control `.env`, database files, and `./data`
- End users must not obtain worker credentials
- Database backup without `.env` should not expose worker tokens, transcripts, or summaries

Audio files on disk are **not encrypted** in the current version.

## Secrets in `.env`

| Variable | Purpose |
| -------- | ------- |
| `HUB_SECRET` | Fernet key material: `SHA-256(secret)` → AES-128-CBC + HMAC for at-rest ciphertext in DB |
| `SESSION_SECRET` | Pepper for hashing session tokens and API token raw values |
| `INSTANCE_BOOTSTRAP_TOKEN` | One-time gate for `POST /setup` |

**Rotating `HUB_SECRET`** makes existing encrypted rows unreadable (worker tokens, transcript JSON, summary bodies, SMTP password). There is no automatic re-encryption.

**Rotating `SESSION_SECRET`** invalidates all session cookies and API tokens (hashes no longer match).

## At-rest encryption

Encrypted columns (via `app/crypto.py`):

- `worker_nodes.api_token_encrypted`
- `transcripts.utterances_encrypted`
- `summaries.body_encrypted`
- `instance_settings.smtp_password_encrypted`

Authorized API responses decrypt on the fly — clients receive plaintext JSON. Encryption protects against DB-only leaks.

## Session cookies

| Property | Value |
| -------- | ----- |
| Name | `hub_session` |
| Flags | `HttpOnly`, `SameSite=Lax`, `Secure` if `COOKIE_SECURE=true` |
| Storage | Raw token never stored; DB holds `SHA-256` hash with `SESSION_SECRET` pepper |
| TTL | 14 days, sliding on each request |

Logout deletes the session row and clears the cookie.

## API tokens

- Created per user: `POST /auth/tokens` (requires org tariff `api_enabled`)
- Shown **once** in create response; only prefix stored for listing
- Bearer auth triggers **rate limits** (per user, IP, global, extra limits on task create)
- Browser cookie sessions are **not** subject to API rate limits
- Revoked tokens: `DELETE /auth/tokens/{id}`

Users with `must_change_password` or expired org password TTL cannot use API tokens.

## Password policy

- Minimum 8 characters on setup, signup, change, reset
- Org can set `password_ttl_days` — after deadline, only password change (+ `/me`, logout) allowed
- Org admin can force reset (`must_change_password`) via reset-password endpoint

Password reset email requires SMTP configured in Instance settings; otherwise `recovery_disabled`.

## Authorization layers

1. **Authentication** — valid session or Bearer token
2. **Org membership** — most features require `ctx.require_org()`
3. **Role** — `org_admin` vs `org_member` vs `instance_admin`
4. **Object ownership / share** — see [roles-and-access](../domain/roles-and-access.md)

Instance admin powers are disabled while **impersonating** (`is_instance_admin` false during impersonation).

## Impersonation

Instance admin: `POST /impersonate` with `user_id` sets `sessions.impersonate_user_id`. Effective user becomes the target; actor remains the admin. Audit log records actions with actor and on-behalf-of.

Stop: `DELETE /impersonate`.

## Rate limiting

In-memory token buckets (single process). Configurable in Instance → Settings. Auth endpoints limited by email + IP + global; Bearer API by user + IP + global.

On exceed: HTTP **429**, `error.code = rate_limited`, header `Retry-After`.

See [deployment](../operations/deployment.md#rate-limiting) and project README.

## Client IP behind proxy

Default: `request.client.host` (often the reverse proxy). Per-IP limits are **0 (off)** by default until configured. Do not trust `X-Forwarded-For` unless the hub is not directly reachable from the internet (future trusted-proxy support may be added).

## Audit log

`audit_log` table records sensitive actions (setup, wallet changes, wipes, impersonation, summary edits). Not exposed via public API in current version — query DB directly for forensics.

## Related pages

- [Roles and access](../domain/roles-and-access.md)
- [Deployment](../operations/deployment.md)
