# Web UI (React + Vite)

SPA for idigest-hub. Run the API from the repo root first (`./.venv/bin/python -m app.serve`).

```bash
npm ci          # or npm install
npm run dev     # http://127.0.0.1:5173 — proxies /api to hub (default :8080; set HUB_PORT if needed)
```

Other scripts: `npm run build`, `lint`, `test`, `check:ui`, `generate:api` (refresh `openapi/openapi.json` + `src/openapi/schema.gen.ts` after backend API changes — see [Frontend docs](../docs/en/development/frontend.md#api-types-openapi)).

**Docs:** [Frontend (EN)](../docs/en/development/frontend.md) · [Frontend (RU)](../docs/ru/development/frontend.md) · [Dev setup](../docs/en/development/setup.md) · [Project README](../README.md)
