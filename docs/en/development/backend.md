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
├── crypto.py         # Envelope encryption (KEK/DEK)
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
│   ├── crypto.py     # DEK management API (instance_admin)
│   ├── oauth.py      # OAuth 2.1 authorize / token / DCR / well-known
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
    ├── crypto_bootstrap.py  # Startup validate + initial DEK + KEK re-wrap
    ├── crypto_reencrypt.py  # Background DEK rotation job
    ├── sso.py          # OIDC login, state, token exchange
    ├── oauth_provider.py    # Hub OAuth 2.1 authorization server
    ├── oauth_scopes.py      # MCP / JWT scope names
    ├── oauth_pages.py       # HTML login / consent / error for /oauth/authorize
    ├── mcp_integration.py   # Embedded Streamable HTTP MCP at /mcp
    ├── mcp_library.py       # MCP tool business logic (aligned with REST)
    ├── mfa.py          # 2FA policy, challenges, recovery codes
    ├── totp.py         # TOTP secret generation and verification
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
- `via_oauth_token` / `oauth_scopes` — set for hub-issued JWT (MCP and REST Bearer JWT)

Enrollment gates in `require_auth()`: `ALLOWED_WHEN_MUST_CHANGE` and `ALLOWED_WHEN_MFA_ENROLLMENT` whitelist endpoints during password-change and forced-2FA flows.

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
- [MCP tools](../api/mcp.md)
