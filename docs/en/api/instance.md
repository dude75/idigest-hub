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

### GET `/instance/orgs`

List all orgs.

### PATCH `/instance/orgs/{org_id}/tariff`

Assign any non-archived tariff.

### POST `/instance/orgs/{org_id}/wallet`

```json
{ "delta": "100.00" }
```

Adds or subtracts balance. Audit logged.

## Settings

### GET `/instance/settings`

SMTP host/port/user/from/tls (password not returned), `allow_new_orgs`, `public_base_url`, ASR models, rate limit matrix.

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

Instance-wide completed job statistics.

## Base skills

Same CRUD as [skills API](skills.md) under `/skills/base`.

## Related pages

- [Billing domain](../domain/billing.md)
- [Workers operations](../operations/workers.md)
- [Security](../architecture/security.md)
