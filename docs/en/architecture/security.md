# Security

## Threat model (practical)

The hub is designed for **on-premise / private network** deployment:

- Operators control `.env`, database files, and `./data`
- End users must not obtain worker credentials
- Database backup without `.env` should not expose worker tokens, transcripts, or summaries

**Audio blobs:** with `STORAGE_BACKEND=local`, files on disk are **not** app-encrypted. With `STORAGE_BACKEND=s3`, use **server-side encryption** (SSE) on the bucket; the hub does not app-level encrypt audio.

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
- `organizations.sso_client_secret_encrypted`

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
- Bearer auth triggers **rate limits** (per user, IP, global)
- Browser cookie sessions skip Bearer general API limits, but **audio upload** and **task create** use the same write limits as Bearer (`enforce_write_limits`, `rate_limit_api_tasks_*`)
- Revoked tokens: `DELETE /auth/tokens/{id}`

Users with `must_change_password` or expired org password TTL cannot use API tokens.

## Password policy

- Minimum 8 characters on setup, signup, change, reset
- Password change, email reset confirm, and org admin reset-password revoke all browser sessions and API tokens for that user
- Org can set `password_ttl_days` — after deadline, only password change (+ `/me`, logout) allowed
- Org admin can force reset (`must_change_password`) via reset-password endpoint

Password reset email requires SMTP **and** **Public URL** in Instance settings (`smtp_configured`); otherwise `recovery_disabled`.

## Single sign-on (SSO)

Per-organization OIDC (Keycloak-compatible). Client secrets stored encrypted (`sso_client_secret_encrypted`). OAuth state/nonce in signed cookies (10 min TTL).

| Rule | Behavior |
| ---- | -------- |
| SSO enabled + configured | `org_member` password login → `sso_login_required` |
| Break-glass | `org_admin` and `instance_admin` keep password login |
| Auto-provision | New email from IdP → `org_member` in that org |
| Callback | `{public_base_url}/api/v1/auth/sso/{org_id}/callback` |
| `id_token` nonce | Required; must match the nonce from the signed OAuth state (fail-closed) |

Requires instance **Public URL** — same as password-reset links and SSO member login URL.

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

Default: `request.client.host` (TCP peer). With empty `TRUSTED_PROXIES` (default), `X-Forwarded-For` / `X-Real-IP` are ignored — safe when the hub is directly reachable. Set `TRUSTED_PROXIES` to the proxy IPs/CIDRs the hub sees (e.g. `127.0.0.1,::1` with nginx on the same host) and configure the proxy headers; see [`deploy/nginx/idigest-hub.conf.example`](../../../deploy/nginx/idigest-hub.conf.example). Per-IP limits are **0 (off)** by default until configured in Instance → Settings.

## Audit log

`audit_log` table records sensitive actions (setup, wallet changes, wipes, impersonation, summary edits). Not exposed via public API in current version — query DB directly for forensics.

## Related pages

- [Roles and access](../domain/roles-and-access.md)
- [Deployment](../operations/deployment.md)
