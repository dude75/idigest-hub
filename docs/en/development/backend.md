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
├── schemas/          # Pydantic response/request models for OpenAPI (e.g. auth_api, org_api, oauth_api)
├── routers/
│   ├── auth/         # setup, session, MFA, me, tokens (package; mounted via auth/_router.py)
│   ├── instance/     # workers, tariffs, orgs, settings, audit, …
│   ├── tasks.py
│   ├── library.py
│   ├── org.py
│   ├── crypto.py     # DEK management API (instance_admin)
│   ├── oauth.py      # OAuth 2.1 — JSON in OpenAPI; HTML authorize/login/SSO excluded
│   ├── public.py     # Guest public summary links (no session)
│   ├── skills.py
│   └── tags.py       # Personal tag catalog + object-tags
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
    ├── storage.py      # Audio blobs: local filesystem or S3 (STORAGE_BACKEND)
    ├── worker_impact.py   # Worker delete/change impact + remediation
    └── tariff_impact.py   # Tariff delete impact + org reassignment
```

## Request path

1. Router endpoint (`require_auth` dependency)
2. Business checks via `AuthContext` helpers
3. DB mutation via `Session` from `get_session`
4. Return a **Pydantic model** (or dict only for legacy/internal helpers). Public routes use `response_model=…` from `app/schemas/`.

Presenters (`presenters.py`) still shape many entities; prefer reusing or wrapping them when building schema models.

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

Always use `floor_money` from `app/money.py` for wallet operations.

## Adding an endpoint

1. Add route to the appropriate router (or submodule under `routers/auth/`, `routers/instance/`, …).
2. Extend `ErrorCode` if there is a new failure mode; add strings to `app/locales/{en,ru,es}.json`.
3. For a **new or changed JSON response shape**:
   - Add or extend a model in `app/schemas/` (often `*_api.py`).
   - Set `response_model=…` on the route; use `include_in_schema=False` only for HTML, redirects, or internal routes (see `oauth.py`).
   - Regenerate the committed OpenAPI snapshot and frontend types (below).
4. Keep business logic in `services/`; use presenters where they already exist.
5. Add pytest coverage in `tests/`. If the route is part of the public contract, extend `tests/test_export_openapi.py` with a `$ref` check for the path.

### OpenAPI export (backend + web types)

From repo root (uses `.venv`, no running server):

```bash
./.venv/bin/python scripts/export_openapi.py   # → web/openapi/openapi.json
cd web && npm run generate:api-types             # → web/src/openapi/schema.gen.ts
```

Or from `web/`: `npm run generate:api` (runs both steps). Commit `openapi.json` and `schema.gen.ts` when the API contract changes. See [Frontend — API types](frontend.md#api-types-openapi).

## Related pages

- [Database](../operations/database.md)
- [Testing](testing.md)
- [Frontend layout](frontend.md)
- [MCP tools](../api/mcp.md)
