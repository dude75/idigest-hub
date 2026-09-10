# Development setup

## Prerequisites

- Python 3.12 with venv at `.venv`
- Node.js 22+
- Use `./.venv/bin/python` and `./.venv/bin/pip` only (project convention)

## Backend

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` — minimal local values:

```env
HUB_SECRET=dev-secret
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

Keep API on 8080. Vite proxies `/api` to the hub:

```bash
cd web
npm install
npm run dev
```

Open Vite URL (typically `http://127.0.0.1:5173`). Hot reload for React.

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

With server running: `http://127.0.0.1:8080/openapi.json`

## Related pages

- [Backend layout](backend.md)
- [Frontend layout](frontend.md)
- [Testing](testing.md)
