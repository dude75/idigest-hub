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

Bind the hub to **localhost only** (`127.0.0.1:8080`) and set `TRUSTED_PROXIES=127.0.0.1,::1` in `.env` so per-IP rate limits use real client IPs from proxy headers. Empty `TRUSTED_PROXIES` keeps the safe default (ignore forwarded headers).

Full example site config: [`deploy/nginx/idigest-hub.conf.example`](../../../deploy/nginx/idigest-hub.conf.example).

Minimal nginx location:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 1024m;
}
```

Hub does not terminate TLS itself in the default setup.

### Security headers (HSTS, CSP)

The full nginx example adds recommended headers on the HTTPS `server` block:

| Header | Purpose |
| ------ | ------- |
| `Strict-Transport-Security` (HSTS) | Browser remembers the site is HTTPS-only |
| `Content-Security-Policy` (CSP) | Restricts script/style/media sources — mitigates XSS |
| `X-Content-Type-Options` | Disables MIME sniffing |
| `X-Frame-Options` | Clickjacking protection (iframe embedding) |
| `Referrer-Policy` | Controls the `Referer` header on navigation |

The hub does not set these itself — configure them on the reverse proxy. The example CSP targets the same-origin SPA from `web/dist` (`'self'`); org SSO via IdP redirect does not need extra CSP directives.

- **Public HTTPS** — enable HSTS and CSP from the example; smoke-test the UI after deploy (login, SSO, audio upload, `/docs`).
- **Private network only** — recommended hardening, not a blocker; use HSTS `includeSubDomains` only if every subdomain is on HTTPS.
- **Verify:** `curl -sI https://hub.example.com | grep -iE 'strict-transport|content-security'`

If you later add external CDNs or scripts, widen `Content-Security-Policy`. Swagger UI (`/docs`) under a strict CSP may need a separate `location` with a relaxed policy.

Set **Public URL** in Instance → Settings to the external base URL users and Keycloak reach (e.g. `https://hub.example.com`). Required for org SSO, password-reset email links, and correct OAuth redirect URIs. See [README — Public URL](../../../README.md#public-url-instance-admin).

## Environment variables

Full table in [README — `.env`](../../../README.md#env). Critical secrets:

- `HUB_SECRET` — set once; backup `.env`
- `SESSION_SECRET` — rotation logs everyone out
- `INSTANCE_BOOTSTRAP_TOKEN` — one-time setup only

Process env changes require restart.

## Data persistence

Under `{DATA_DIR}` (default `./data`):

| Path | Content |
| ---- | ------- |
| `hub.db` | SQLite database |
| `pg/` | PostgreSQL files (compose profile) |
| `logs/` | Rotating `app.log` |
| `uploads/{audio_id}/` | Uploaded audio (**local backend only**) |

With **`STORAGE_BACKEND=s3`**, audio lives in the configured bucket (server-side encryption). The hub downloads to a temp file when streaming to transcribe workers — worker API is unchanged.

**Backup strategy:** stop hub (optional but safer), copy `./data` + bucket contents (if S3) + secure copy of `.env`.

## Rate limiting

Configured in Instance → Settings UI (stored in DB). Enforced in RAM — restart clears counters.

Auth traffic: email + IP + global buckets. Bearer API: user + IP + global. Upload and task-create limits apply to **both** Bearer tokens and browser sessions.

`/api/v1/health` and static assets are excluded.

## Scaling limits

Current architecture targets **single-node** deployment:

- One dispatcher loop
- In-memory rate limiter
- Local filesystem or S3-compatible object storage for audio (`STORAGE_BACKEND`)

Horizontal scaling would require shared rate-limit store and single dispatcher leader — S3 removes the need for shared filesystem for uploads, but multi-replica hub is still not supported out of the box.

## API exploration

- OpenAPI JSON: `GET /openapi.json`
- Swagger UI: `/docs` (Authorize with session cookie or Bearer `idg_…` token)

## Related pages

- [Database](database.md)
- [Workers](workers.md)
- [Troubleshooting](troubleshooting.md)
