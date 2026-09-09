# Deployment

Quick start lives in the project [README](../../../README.md). This page adds production-oriented notes.

## Runtime requirements

| Component | Version |
| --------- | ------- |
| Python | 3.12 |
| Node.js | 22+ (build time only) |
| Uvicorn workers | **1** always |

Multi-worker breaks in-memory rate limits and dispatcher locking assumptions.

## Local production-like run

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cd web && npm ci && npm run build && cd ..
cp .env.example .env   # fill secrets
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --workers 1
```

SPA served from `web/dist` by the same process.

## Docker Compose

See README sections **Docker Compose**. Summary:

- Image runs as uid/gid **1001**
- Mount `./data:/data` for DB, logs, uploads
- Default SQLite inside container: `sqlite:////data/hub.db`
- PostgreSQL optional: `docker compose --profile pg up`

Fix permissions if needed:

```bash
sudo chown -R 1001:1001 ./data
```

## HTTPS reverse proxy

Set `COOKIE_SECURE=true` when serving over HTTPS so session cookies get the `Secure` flag.

Example nginx location:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 1024m;
}
```

Hub does not terminate TLS itself in the default setup.

Set **Public URL** in Instance → Settings to the external base URL users and Keycloak reach (e.g. `https://hub.example.com`). Required for org SSO, password-reset email links, and correct OAuth redirect URIs. See [README — Public URL](../../../README.md#public-url-instance-admin).

## Environment variables

Full table in [README — `.env`](../../../README.md#env). Critical secrets:

- `HUB_SECRET` — set once; backup `.env`
- `SESSION_SECRET` — rotation logs everyone out
- `INSTANCE_BOOTSTRAP_TOKEN` — one-time setup only

Process env changes require restart.

## Data persistence

Everything under `{DATA_DIR}` (default `./data`):

| Path | Content |
| ---- | ------- |
| `hub.db` | SQLite database |
| `pg/` | PostgreSQL files (compose profile) |
| `logs/` | Rotating `app.log` |
| `uploads/{audio_id}/` | Uploaded audio |

**Backup strategy:** stop hub (optional but safer), copy entire `./data` + secure copy of `.env`.

## Rate limiting

Configured in Instance → Settings UI (stored in DB). Enforced in RAM — restart clears counters.

Auth traffic: email + IP + global buckets. Bearer API: user + IP + global. Upload and task-create limits apply to **both** Bearer tokens and browser sessions.

`/api/v1/health` and static assets are excluded.

## Scaling limits

Current architecture targets **single-node** deployment:

- One dispatcher loop
- In-memory rate limiter
- Local filesystem uploads

Horizontal scaling would require shared storage, shared rate-limit store, and single dispatcher leader — not supported out of the box.

## API exploration

- OpenAPI JSON: `GET /openapi.json`
- Swagger UI: `/docs` (Authorize with session cookie or Bearer `idg_…` token)

## Related pages

- [Database](database.md)
- [Workers](workers.md)
- [Troubleshooting](troubleshooting.md)
