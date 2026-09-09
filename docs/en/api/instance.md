# Instance API

Auth required. Caller must be **instance_admin** (not impersonating).

## Workers

### GET `/workers`

List worker nodes (no api_token in response).

### POST `/workers`

```json
{
  "type": "transcribe",
  "name": "GPU node 1",
  "base_url": "http://host.docker.internal:8000",
  "api_token": "worker-secret",
  "weight": 2,
  "enabled": true
}
```

`type`: `transcribe` | `summarize`. Token encrypted at rest.

### PATCH `/workers/{id}`

Update fields; omit `api_token` to keep existing.

### DELETE `/workers/{id}`

Remove node (does not cancel in-flight hub tasks automatically).

## Tariffs

### GET `/tariffs`

All tariffs with org counts.

### POST `/tariffs`

Create tariff (prices as decimal strings).

### PATCH `/tariffs/{id}`

Update fields.

### POST `/tariffs/{id}/archive`

### POST `/tariffs/{id}/unarchive`

### DELETE `/tariffs/{id}`

Fails with `tariff_in_use` or `last_tariff` if blocked.

## Organizations

### GET `/orgs`

List all orgs with embedded tariff and member list.

### PATCH `/orgs/{org_id}/tariff`

Assign any non-archived tariff.

### POST `/orgs/{org_id}/wallet`

```json
{ "delta": "100.00" }
```

Adds or subtracts balance. Audit logged.

### GET `/orgs/{org_id}/ledger`

Wallet ledger for one org: usage charges and instance-admin top-ups.

Query (same date semantics as stats):

| Param | Description |
| ----- | ----------- |
| `from` | Start date `YYYY-MM-DD` |
| `to` | End date inclusive |
| `user_id` | Filter charges by member |
| `kind` | `transcribe` or `summarize` |

Returns `{ "entries": [...], "total_spent", "total_topup", "net" }`. Entry types: `charge` (usage) and `wallet` (manual delta).

## Settings

### GET `/instance/settings`

SMTP host/port/user/from/tls (password not returned), `allow_new_orgs`, `public_base_url`, ASR models, rate limit matrix. Also `smtp_configured`: true only when host, from-address, **and** `public_base_url` are set (required for password reset emails).

### PATCH `/instance/settings`

Partial update. Fields include:

- `allow_new_orgs`, `public_base_url`
- SMTP: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `smtp_tls`
- Models: `asr_model`, `diarization_model`
- Rate limits: `rate_limit_enabled`, `rate_limit_login_email`, … (see README)

Changing rate limits invalidates in-memory limit cache.

## Impersonation

### POST `/impersonate`

```json
{ "user_id": "uuid" }
```

Session acts as target user. Admin UI shows impersonation banner.

### DELETE `/impersonate`

Return to admin identity.

## Stats

### GET `/instance/stats`

Instance-wide usage statistics from `usage_events`.

Query:

| Param | Description |
| ----- | ----------- |
| `from` | Start date `YYYY-MM-DD` (UI defaults to last 7 days) |
| `to` | End date inclusive |
| `org_id` | Filter by organization |
| `user_id` | Filter by user |
| `kind` | `transcribe` or `summarize` |

Returns org/user counts, queued/running tasks, daily breakdown, totals (`transcribe_done`, `summarize_done`, `audio_sec`, `summary_chars`, `usage_total`).

## Base skills

Same CRUD as [skills API](skills.md) under `/skills/base`.

## Related pages

- [Billing domain](../domain/billing.md)
- [Workers operations](../operations/workers.md)
- [Security](../architecture/security.md)
