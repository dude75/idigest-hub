# Deployment

Quick start lives in the project [README](../../../README.md). This page adds production-oriented notes.

## Runtime requirements

| Component | Version |
| --------- | ------- |
| Python | 3.12 |
| Node.js | 22+ (build time only) |
| Uvicorn workers | **1** always |

Multi-worker breaks in-memory rate limits, dispatcher locking assumptions, and **Telegram long polling** (each process runs its own `getUpdates` loop with an in-memory offset).

## Local production-like run

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cd web && npm ci && npm run build && cd ..
cp .env.example .env   # fill secrets
./.venv/bin/python -m app.serve
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

By default the hub listens on HTTP. Edge TLS belongs on the reverse proxy (see the nginx example).

### TLS on the hub (nginx → hub over LAN)

When the hub runs on a separate host and traffic between nginx and the hub crosses the LAN, enable HTTPS on the hub via `.env` (both paths required; self-signed PEM is fine):

```env
PORT=8443
SSL_CERTFILE=/data/certs/hub.crt
SSL_KEYFILE=/data/certs/hub.key
COOKIE_SECURE=true
TRUSTED_PROXIES=10.0.1.10
```

`TRUSTED_PROXIES` is the nginx LAN IP (not `127.0.0.1` when the proxy is on another host). Mount the cert directory into the container, e.g. `./certs:/data/certs:ro`. The process starts via `python -m app.serve` (default Docker CMD).

On nginx:

```nginx
upstream idigest_hub {
    server 10.0.1.50:8443;
}

location / {
    proxy_pass https://idigest_hub;
    proxy_ssl_verify on;
    proxy_ssl_trusted_certificate /etc/ssl/certs/hub.crt;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Set **Public URL** in Instance → Settings to the **external** nginx address (`https://hub.example.com`), not the internal `:8443`.

**Telegram webhooks** use the same public hostname: Telegram must reach `https://…/api/v1/integrations/telegram/webhook` on port **443**. If the path works from your network but `getWebhookInfo` reports `Connection timed out`, disable **Deliver updates via webhook** in Instance → Telegram (long polling — only with a **single** hub process). With **multiple replicas** behind a load balancer, keep webhook enabled; long polling is not supported when `replicas > 1` or `workers > 1`. See [Troubleshooting — Telegram](troubleshooting.md#telegram-bot).

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

- **Public HTTPS** — enable HSTS and CSP from the example; smoke-test the UI after deploy (login, 2FA verify/enroll if enabled, SSO, audio upload, `/docs`).
- **Private network only** — recommended hardening, not a blocker; use HSTS `includeSubDomains` only if every subdomain is on HTTPS.
- **Verify:** `curl -sI https://hub.example.com | grep -iE 'strict-transport|content-security'`

If you later add external CDNs or scripts, widen `Content-Security-Policy`. Swagger UI (`/docs`) under a strict CSP may need a separate `location` with a relaxed policy.

Set **Public URL** in Instance → Settings to the external base URL users and Keycloak reach (e.g. `https://hub.example.com`). Required for org SSO, password-reset email links, public summary links, and MCP / OAuth 2.1 (`{public_url}/mcp`). See [README — Public URL](../../../README.md#public-url-instance-admin).

## Environment variables

Full table in [README — `.env`](../../../README.md#env). Critical secrets:

- `HUB_SECRET` — KEK for envelope encryption; backup `.env`; wrong value blocks startup when DEKs/data exist
- `HUB_SECRET_PREV` — previous KEK during rotation only; remove after DEK re-wrap completes
- `SESSION_SECRET` — required before `/setup`; rotation logs everyone out; empty value blocks startup when sessions or API tokens exist
- `INSTANCE_BOOTSTRAP_TOKEN` — one-time setup only
- `OPENAPI_ENABLED` — default `false`; set `true` locally for `/docs`, `/redoc`, and `/openapi.json`
- `OAUTH_PROVIDER_ENABLED=true` — enable hub OAuth 2.1 + MCP at `/mcp` (requires Public URL)
- `OAUTH_SIGNING_KEY_PEM` — optional RSA PEM; otherwise the hub writes `{DATA_DIR}/oauth_signing_key.pem`

Process env changes require restart.

## Data persistence

Under `{DATA_DIR}` (default `./data`):

| Path | Content |
| ---- | ------- |
| `hub.db` | SQLite database |
| `pg/` | PostgreSQL files (compose profile) |
| `logs/` | Rotating `app.log` |
| `uploads/{audio_id}/` | Uploaded audio (**local backend only**) |
| `tmp/` | Ephemeral import/ffmpeg and S3 worker staging; `tmp/cache/yt-dlp` is yt-dlp cache (safe to wipe while stopped; YouTube may require cookies again) |

Compose sets `TMPDIR=/data/tmp` so the process does not grow the container writable layer.

With **`STORAGE_BACKEND=s3`**, audio lives in the configured bucket (server-side encryption). The hub downloads to `{DATA_DIR}/tmp` when streaming to transcribe workers — worker API is unchanged.

**Backup strategy:** stop hub (optional but safer), copy `./data` + bucket contents (if S3) + secure copy of `.env`.

### Migrating audio between local disk and S3

Offline CLI scripts copy blobs under the `uploads/` prefix only (same layout as the hub: `{DATA_DIR}/uploads/{audio_id}/original{suffix}` ↔ `s3://{bucket}/uploads/...`). They read **`DATA_DIR`** and **`S3_*`** from `.env`; **`STORAGE_BACKEND`** is not changed by the scripts — set it after copying and restart the hub.

Stop the hub before a bulk sync to avoid concurrent writes.

| Direction | Script |
| --------- | ------ |
| S3 → local | `scripts/storage_sync_s3_to_local.py` |
| local → S3 | `scripts/storage_sync_local_to_s3.py` |

Use **`--dry-run`** first to list transfers. By default, files are skipped when the destination already exists with the **same size**; use **`--overwrite`** to force. Uploads to S3 honour **`S3_SSE`** / **`S3_SSE_KMS_KEY_ID`** when set.

#### Docker Compose

Scripts ship in the hub image at `/app/scripts/`. Compose mounts **`./data:/data`** and sets **`DATA_DIR=/data`**; `S3_*` come from **`env_file: .env`**. Local uploads land in **`./data/uploads`** on the host.

From the directory that contains `docker-compose.yml` and `.env`:

```bash
docker compose stop idigest-hub

docker compose run --rm --no-deps idigest-hub \
  python scripts/storage_sync_s3_to_local.py --dry-run

docker compose run --rm --no-deps idigest-hub \
  python scripts/storage_sync_s3_to_local.py
```

Replace the script name with `storage_sync_local_to_s3.py` for the opposite direction. Then update **`STORAGE_BACKEND`** in `.env` if needed and `docker compose up -d idigest-hub`.

Prefer **`docker compose run`** over **`exec`** while the main hub is stopped — avoids concurrent writes. **`--no-deps`** skips waiting for the optional Postgres profile (storage sync does not use the DB). Rebuild the image (`docker compose build idigest-hub`) if the image predates these scripts.

**S3 endpoint from inside the container:** `localhost` in **`S3_ENDPOINT`** refers to the container, not the host. For MinIO or similar on the host, use a reachable URL (e.g. `http://host.docker.internal:9000` on Docker Desktop, or the host LAN IP on Linux).

**File ownership:** the hub container runs as **uid/gid 1001**. Sync via Compose creates files owned by 1001. If you run scripts on the host instead, ensure `./data/uploads` remains writable by 1001 (`chown -R 1001:1001 ./data` if needed).

#### Native install (venv)

From the repo root with the project venv (needs `boto3`):

```bash
./.venv/bin/python scripts/storage_sync_s3_to_local.py --dry-run
```

Use **`DATA_DIR=./data`** in `.env` so paths match the Compose bind mount.

The scripts do **not** update `storage_path` values in the database. After switching backends, existing rows must already reference the correct form (absolute path for `local`, `s3://…` for `s3`). Typical greenfield moves (empty bucket before enabling S3, or fresh local tree before enabling `local`) need only the sync + `STORAGE_BACKEND` change; migrating an instance that already stored paths for the old backend requires a separate DB update.

See also [Backend — operational CLI](../development/backend.md#operational-cli).

## Rate limiting

Configured in Instance → Settings UI (stored in DB). Enforced in RAM — restart clears counters.

Auth traffic: email + IP + global buckets. Bearer API: user + IP + global. Upload and task-create limits apply to **both** Bearer tokens and browser sessions.

`/api/v1/health` and static assets are excluded.

## Scaling limits

Current architecture targets **single-node** deployment:

- One dispatcher loop
- In-memory rate limiter
- Local filesystem or S3-compatible object storage for audio (`STORAGE_BACKEND`)
- **Telegram:** webhook is fine with a shared database and one public URL behind a load balancer; long polling requires a single process. Bot in-memory state (multi-step flows) is not shared across replicas.

Horizontal scaling would require shared rate-limit store and single dispatcher leader — S3 removes the need for shared filesystem for uploads, but multi-replica hub is still not supported out of the box. If you later run multiple replicas, use **webhook** delivery for the bot, not long polling.

## API exploration

OpenAPI is **off by default** (`OPENAPI_ENABLED=false`). To explore the API locally, set `OPENAPI_ENABLED=true`:

- OpenAPI JSON: `GET /openapi.json`
- Swagger UI: `/docs` (Authorize with session cookie or Bearer `idg_…` token)

## Related pages

- [Database](database.md)
- [Workers](workers.md)
- [Troubleshooting](troubleshooting.md)
