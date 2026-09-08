# API overview

Base path: **`/api/v1`**

Interactive OpenAPI schema: `{origin}/openapi.json` (FastAPI auto-generated).

## Response envelope

### Success

Most endpoints return JSON objects directly, e.g. `{ "status": "ok" }` or entity payloads.

Task create returns **202** with task body (not wrapped).

### Error

```json
{
  "status": "error",
  "error": {
    "code": "not_found",
    "message": "Human-readable localized message"
  }
}
```

`message` follows `Accept-Language` / user locale (`en`, `ru`, `es`).

## Authentication

| Method | Header / cookie | Rate limited |
| ------ | ----------------- | ------------ |
| Session | Cookie `hub_session` | Auth endpoints only |
| API token | `Authorization: Bearer <token>` | Yes (Bearer rules) |

Unauthenticated requests to protected routes → **401** `unauthorized`.

## Common HTTP status codes

| Status | When |
| ------ | ---- |
| 200 | OK |
| 202 | Task accepted |
| 400 | `validation_error`, bad input |
| 401 | Auth failures, `bootstrap_invalid` |
| 403 | `forbidden`, `signup_disabled`, `api_disabled`, `must_change_password` |
| 404 | `not_found` |
| 409 | `conflict`, `email_taken`, `setup_already_done`, `task_running`, … |
| 413 | `payload_too_large`, `text_too_long` |
| 429 | `rate_limited`, `insufficient_balance` |

## Error codes

| code | HTTP | Meaning |
| ---- | ---- | ------- |
| `unauthorized` | 401 | Missing/invalid session or token |
| `invalid_credentials` | 401 | Wrong email/password |
| `bootstrap_invalid` | 401 | Wrong bootstrap token on setup |
| `forbidden` | 403 | Insufficient role |
| `must_change_password` | 403 | Password change required |
| `signup_disabled` | 403 | Signup closed |
| `recovery_disabled` | 403 | SMTP not configured |
| `api_disabled` | 403 | Tariff disables API |
| `not_found` | 404 | Resource or route |
| `validation_error` | 400 | Invalid body/query |
| `invalid_file` | 400 | Bad upload |
| `payload_too_large` | 413 | Upload too big |
| `text_too_long` | 413 | Summarize input too large |
| `insufficient_balance` | 429 | Wallet empty |
| `rate_limited` | 429 | Too many requests (+ `Retry-After`) |
| `setup_already_done` | 409 | Bootstrap already completed |
| `email_taken` | 409 | Duplicate email |
| `tariff_not_available` | 400 | Invalid tariff choice |
| `last_org_admin` | 409 | Would remove last admin |
| `tariff_in_use` | 409 | Cannot delete tariff |
| `last_tariff` | 409 | Cannot delete last tariff |
| `task_running` | 409 | Cancel rejected |
| `conflict` | 409 | Generic conflict |

Task-level errors (worker pipeline) appear on task object as `error.code`, not always in this enum.

## Health

```
GET /api/v1/health
```

No auth. Returns `{ "status": "ok", "version": "..." }`.

## Endpoint index

| Area | Doc |
| ---- | --- |
| Setup, auth, me, tokens | [auth.md](auth.md) |
| Tasks | [tasks.md](tasks.md) |
| Audio, transcripts, summaries, shares | [library.md](library.md) |
| Organization admin | [org.md](org.md) |
| Instance admin | [instance.md](instance.md) |
| Skills catalog | [skills.md](skills.md) |

## Conventions

- UUIDs as strings everywhere
- Money as decimal strings in JSON (`"12.34"`)
- Timestamps ISO 8601 with timezone
- Email normalized to lowercase on write

## Related pages

- [Security](../architecture/security.md)
- [Development setup](../development/setup.md)
