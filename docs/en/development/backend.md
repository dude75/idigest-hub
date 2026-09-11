# Backend layout

Python package: `app/`

```
app/
├── main.py           # FastAPI app, lifespan, SPA fallback, middleware
├── config.py         # pydantic-settings from .env
├── constants.py      # TTLs, limits, locales
├── models.py         # SQLAlchemy ORM
├── db.py             # Engine, session, init_database (Alembic)
├── deps.py           # AuthContext, require_auth
├── errors.py         # ErrorCode enum, ApiError
├── presenters.py     # Entity → JSON
├── crypto.py         # Fernet encrypt/decrypt
├── security.py       # Passwords, token hashing
├── cookies.py        # Session cookie helpers
├── i18n.py           # Locale negotiation + translations
├── rate_limit.py     # In-memory limiter
├── openapi.py        # Swagger security schemes (Bearer + session cookie)
├── routers/
│   ├── auth.py
│   ├── tasks.py
│   ├── library.py
│   ├── org.py
│   ├── instance.py
│   └── skills.py
└── services/
    ├── dispatcher.py   # Task queue loop
    ├── workers.py      # httpx2 client to workers
    ├── billing.py
    ├── access.py
    ├── artifacts.py    # Hard delete
    ├── offboarding.py
    ├── retention.py
    ├── audit.py
    ├── mail.py
    ├── stats.py
    ├── sso.py          # OIDC login, state, token exchange
    ├── backup.py       # Profile ZIP/TGZ archives
    ├── export.py       # Download filenames, markdown fence unwrap
    └── storage.py      # Audio blobs: local filesystem or S3 (STORAGE_BACKEND)
```

## Request path

1. Router endpoint (`require_auth` dependency)
2. Business checks via `AuthContext` helpers
3. DB mutation via `Session` from `get_session`
4. Return `presenters.*_public()` dict

Task endpoints additionally `await locked_tick()` to progress queue synchronously.

## AuthContext

Central authorization object (`app/deps.py`):

- `user` — effective user (target when impersonating)
- `actor` — logged-in user
- `org` / `membership` — tenant context
- `is_instance_admin`, `is_org_admin` — role shortcuts

## Background work

`dispatcher_loop` started in lifespan — independent of HTTP workers count (must still be 1).

Uses `asyncio.Lock` (`tick_lock`) so HTTP-triggered ticks and background ticks do not overlap.

## Internationalization

Server strings: `app/locales/{en,ru,es}.json`. Client strings: `web/src/locales/`.

`t(locale, error_code)` produces API error messages.

## Money

Always use `floor_to_cents` from `app/money.py` for wallet operations.

## Adding an endpoint

1. Add route to appropriate router
2. Extend `ErrorCode` if new failure mode
3. Add translations to locale JSON files
4. Add presenter if new entity shape
5. Write pytest coverage in `tests/`

## Related pages

- [Database](../operations/database.md)
- [Testing](testing.md)
