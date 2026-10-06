# Development setup

## Prerequisites

- Python 3.12 with venv at `.venv`
- Node.js 22+
- Use `./.venv/bin/python` and `./.venv/bin/pip` only (project convention)

## Backend

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
```

Edit `.env` — minimal local values:

```env
HUB_SECRET=dev-secret
# HUB_SECRET_PREV=   # only during KEK rotation in production
INSTANCE_BOOTSTRAP_TOKEN=dev-bootstrap
SESSION_SECRET=dev-session
DATABASE_URL=sqlite:///./data/hub.db
DATA_DIR=./data
```

```bash
mkdir -p data/uploads data/logs
./.venv/bin/python -m app.serve
```

Bootstrap: open `http://127.0.0.1:8080/setup` or POST `/api/v1/setup`.

## Frontend (Vite dev server)

Keep the API running (default port `8080`). From `web/`, Vite proxies `/api` to `http://127.0.0.1:<port>`, where `<port>` is `HUB_PORT`, then `PORT`, then `8080` (see `web/vite.config.ts`). Env files are loaded from `web/`; if the hub uses another port from the repo-root `.env`, set `HUB_PORT` in `web/.env.local` or in the shell when starting Vite.

```bash
cd web
npm install
npm run dev
```

Open Vite URL (typically `http://127.0.0.1:5173`). Hot reload for React.

Before pushing UI changes, run the same checks as CI:

```bash
cd web && npm run lint && npm run check:ui && npm test && npm run build
```

See [web/README.md](../../../web/README.md) and [frontend.md](frontend.md) for the shadcn / App\* conventions.

Production build:

```bash
cd web && npm ci && npm run build
```

Output: `web/dist/` — served by FastAPI when present.

## Tests

```bash
./.venv/bin/pytest
```

Uses isolated SQLite DB per test via `tests/conftest.py` (see [testing.md](testing.md)).

## Migrations

After model changes:

```bash
./.venv/bin/alembic revision --autogenerate -m "description"
./.venv/bin/alembic upgrade head
```

## OpenAPI

Disabled by default (`OPENAPI_ENABLED=false`). Set `OPENAPI_ENABLED=true` in `.env` and restart; then schema at `http://127.0.0.1:8080/openapi.json`, Swagger UI at `/docs`. See [API overview](../api/README.md).

## Related pages

- [Backend layout](backend.md)
- [Frontend layout](frontend.md)
- [Testing](testing.md)
