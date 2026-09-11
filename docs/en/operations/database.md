# Database

## Engines

| Engine | Connection string example |
| ------ | ------------------------- |
| SQLite (default) | `sqlite:///./data/hub.db` |
| PostgreSQL | `postgresql+psycopg://user:pass@host:5432/hub` |

Set via `DATABASE_URL` in `.env`. Empty legacy fallback: `SQLITE_PATH`.

**Switching URLs creates an empty separate database** — no automatic migration between SQLite and PostgreSQL.

## Schema management

1. **SQLAlchemy models** — `app/models.py` (source of truth for new revisions)
2. **Alembic migrations** — `alembic/versions/`; applied automatically on startup via `init_database()` in `app/db.py` (`alembic upgrade head`)

Existing databases created before Alembic tracking (via the old `ensure_schema()` path) are detected on first startup and stamped to `head` before upgrade.

Local development after model changes:

```bash
./.venv/bin/alembic revision --autogenerate -m "description"
./.venv/bin/alembic upgrade head   # optional; also runs on next app start
```

## Core tables

| Table | Purpose |
| ----- | ------- |
| `instance_settings` | Singleton row (id=1): bootstrap, SMTP, rate limits, ASR models |
| `users` | Accounts |
| `organizations` | Tenants + balance |
| `memberships` | user ↔ org + role |
| `sessions` | Cookie sessions + impersonation |
| `api_tokens` | Bearer tokens (hashed) |
| `tariffs` | Pricing plans |
| `worker_nodes` | External worker registry |
| `tasks` | Hub job queue |
| `audios` | Upload metadata |
| `transcripts` | Encrypted utterances |
| `summaries` | Encrypted bodies |
| `skills` | Prompt templates |
| `shares` / `hidden_items` | Sharing and per-user hide |
| `usage_events` | Billing ledger |
| `audit_log` | Admin actions |
| `password_reset_tokens` | Email recovery |

UUIDs stored as 36-char strings. No soft-delete columns (`deleted_at`).

## Encrypted columns

Require valid `HUB_SECRET`. See [Security](../architecture/security.md).

## SQLite notes

- Single-writer; fits one Uvicorn worker design
- DB file path relative to process CWD unless absolute in URL
- Dispatcher commits frequently — use SSD for `./data`

## PostgreSQL notes

Docker Compose profile `pg` stores data in `./data/pg` (uid **999** inside PG container).

Hub container still uses uid **1001** for uploads/logs.

## Retention job

Dispatcher calls `purge_expired_audio()` each tick — deletes audio past org tariff `audio_retention_days` when not referenced by active tasks.

## Related pages

- [Deployment](deployment.md)
- [Billing](../domain/billing.md)
