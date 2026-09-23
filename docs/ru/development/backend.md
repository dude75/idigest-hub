# Структура backend

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
│   ├── crypto.py     # API управления DEK (instance_admin)
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
    ├── crypto_bootstrap.py  # Validate при старте + первый DEK + KEK re-wrap
    ├── crypto_reencrypt.py  # Фоновый job ротации DEK
    ├── sso.py          # OIDC login, state, token exchange
    ├── oauth_provider.py    # Authorization server OAuth 2.1 хаба
    ├── oauth_scopes.py      # Имена MCP / JWT scope
    ├── oauth_pages.py       # HTML login / consent / ошибка для /oauth/authorize
    ├── mcp_integration.py   # Встроенный Streamable HTTP MCP на /mcp
    ├── mcp_library.py       # Бизнес-логика MCP tools (как REST)
    ├── mfa.py          # 2FA policy, challenges, recovery codes
    ├── totp.py         # TOTP secret generation and verification
    ├── backup.py       # Profile ZIP/TGZ archives
    ├── export.py       # Download filenames, markdown fence unwrap
    └── storage.py      # Audio blobs: local filesystem or S3 (STORAGE_BACKEND)
```

## Путь запроса

1. Router endpoint (`require_auth` dependency)
2. Business checks через helpers `AuthContext`
3. DB mutation через `Session` из `get_session`
4. Return `presenters.*_public()` dict

Task endpoints дополнительно вызывают `await locked_tick()` для синхронного продвижения очереди.

## AuthContext

Центральный объект авторизации (`app/deps.py`):

- `user` — effective user (target при impersonating)
- `actor` — logged-in user
- `org` / `membership` — tenant context
- `is_instance_admin`, `is_org_admin` — role shortcuts
- `via_oauth_token` / `oauth_scopes` — для JWT, выданного хабом (MCP и REST Bearer JWT)

Enrollment gates в `require_auth()`: `ALLOWED_WHEN_MUST_CHANGE` и `ALLOWED_WHEN_MFA_ENROLLMENT` — whitelist endpoints при смене пароля и принудительной настройке 2FA.

## Фоновая работа

`dispatcher_loop` стартует в lifespan — независимо от числа HTTP workers (но всё равно должно быть 1).

Использует `asyncio.Lock` (`tick_lock`), чтобы HTTP-triggered ticks и background ticks не пересекались.

## Internationalization

Server strings: `app/locales/{en,ru,es}.json`. Client strings: `web/src/locales/`.

`t(locale, error_code)` формирует сообщения об ошибках API.

## Money

Всегда используйте `floor_to_cents` из `app/money.py` для операций с wallet.

## Добавление endpoint

1. Добавьте route в соответствующий router
2. Расширьте `ErrorCode`, если нужен новый режим ошибки
3. Добавьте переводы в locale JSON files
4. Добавьте presenter, если новая форма entity
5. Напишите pytest coverage в `tests/`

## Связанные страницы

- [Database](../operations/database.md)
- [Testing](testing.md)
- [MCP tools](../api/mcp.md)
