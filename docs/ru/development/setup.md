# Настройка для разработки

## Предварительные требования

- Python 3.12 с venv в `.venv`
- Node.js 22+
- Используйте только `./.venv/bin/python` и `./.venv/bin/pip` (конвенция проекта)

## Backend

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Отредактируйте `.env` — минимальные локальные значения:

```env
HUB_SECRET=dev-secret
# HUB_SECRET_PREV=   # только при ротации KEK в production
INSTANCE_BOOTSTRAP_TOKEN=dev-bootstrap
SESSION_SECRET=dev-session
DATABASE_URL=sqlite:///./data/hub.db
DATA_DIR=./data
```

```bash
mkdir -p data/uploads data/logs
./.venv/bin/python -m app.serve
```

Bootstrap: откройте `http://127.0.0.1:8080/setup` или POST `/api/v1/setup`.

## Frontend (Vite dev server)

Держите API на 8080. Vite проксирует `/api` на hub:

```bash
cd web
npm install
npm run dev
```

Откройте URL Vite (обычно `http://127.0.0.1:5173`). Hot reload для React.

Production build:

```bash
cd web && npm ci && npm run build
```

Output: `web/dist/` — отдаётся FastAPI, если каталог существует.

## Tests

```bash
./.venv/bin/pytest
```

Использует изолированную SQLite DB на тест через `tests/conftest.py` (см. [testing.md](testing.md)).

## Migrations

После изменений моделей:

```bash
./.venv/bin/alembic revision --autogenerate -m "description"
./.venv/bin/alembic upgrade head
```

## OpenAPI

При запущенном сервере: `http://127.0.0.1:8080/openapi.json`

## Связанные страницы

- [Backend layout](backend.md)
- [Frontend layout](frontend.md)
- [Testing](testing.md)
