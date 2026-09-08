# idigest-hub

On-premise **multi-tenant control plane** over [itranscribe-worker](#attach-workers) and [isummarize-worker](#attach-workers). Users talk only to the hub. The hub owns orgs, roles, wallets, skills, artifacts, and its own task queue (`POST` → **202** + `task_id` → poll). Workers stay external.

**Language:** [English](README.md) · [Русский](README.ru.md)

## What it does

- Signup is **open** by default. SQLite is the out-of-the-box database (`DATABASE_URL=sqlite:///./data/hub.db`). PostgreSQL is optional via the same variable.
- One `instance_admin` is created at first boot (`/setup`). Everyone else is in an organization (`org_admin` / `org_member`).
- Users never see worker URLs or API tokens. The instance admin attaches workers in the UI (base URL + bearer token).
- FastAPI serves the built SPA from the same origin (`web/dist`). Session cookie is HttpOnly + `SameSite=Lax` — no CORS.
- Default HTTP port is **8080** so it does not clash with workers on `8000`.
- Compose runs **only the hub** plus `./data` (and optionally PostgreSQL with profile `pg`). Do not put workers in this stack.

## Requirements

- Python **3.12**
- Virtualenv at `.venv` (use `./.venv/bin/python` and `./.venv/bin/pip` only)
- **Node.js** (22+) to build the SPA in `web/`
- Disk under `./data` for the database file (SQLite), logs, audio uploads, and optionally PostgreSQL data at `./data/pg` (not committed)

## Install and run

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt

cd web
npm ci
npm run build
cd ..
```

Copy `.env.example` → `.env` and fill the secrets (see [`.env`](#env)). Do not commit `.env`. Then:

```bash
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --workers 1
```

Always keep **uvicorn** `--workers 1`. Production serves the SPA from `web/dist` on this same process.

For UI development, leave the API on `8080` and run Vite (proxies `/api` to the hub):

```bash
cd web
npm install
npm run dev
```

Then open the Vite URL (typically `http://127.0.0.1:5173`).

Check:

```bash
curl -s http://127.0.0.1:8080/api/v1/health
```

JSON includes `version` (same as `version.txt`). Docker: [Docker Compose](#docker-compose).

## First-time setup

Until bootstrap is done, open **`/setup`** in the UI (`http://127.0.0.1:8080/setup`) and create the instance admin with `INSTANCE_BOOTSTRAP_TOKEN` from `.env`.

Same call over HTTP:

```bash
curl -sS -X POST http://127.0.0.1:8080/api/v1/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"choose-a-long-password","bootstrap_token":"'"$INSTANCE_BOOTSTRAP_TOKEN"'","locale":"en"}'
```

This can run **once**. After that: HTTP **409** `setup_already_done`. A second instance admin is not created.

## `.env`

Copy names into `.env`. **Do not put real tokens in git or in this README.** Changing a value requires a process restart.

| Variable                     | Meaning                                                                                                                                                          |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HUB_SECRET`                 | At-rest encryption key material (see below). Empty = encrypt/decrypt fails.                                                                                      |
| `INSTANCE_BOOTSTRAP_TOKEN`   | One-time secret for `POST /api/v1/setup` / UI `/setup`. Empty or wrong = `bootstrap_invalid`.                                                                    |
| `SESSION_SECRET`             | Pepper for session and API-token hashes. Changing it invalidates existing cookies and tokens.                                                                    |
| `HOST`                       | Bind address (`127.0.0.1` locally; Docker uses `0.0.0.0`).                                                                                                       |
| `PORT`                       | HTTP port (default `8080`).                                                                                                                                      |
| `DATA_DIR`                   | Persistent root (default `./data`): logs, uploads at `{DATA_DIR}/uploads/{audio_id}/`. SQLite file lives under this tree when using the default URL. |
| `DATABASE_URL`               | SQLAlchemy URL (default `sqlite:///./data/hub.db`). Use `postgresql+psycopg://user:pass@host:5432/db` for PostgreSQL. **Switching URL uses a different database with different data** — there is no automatic SQLite ↔ PostgreSQL migration. |
| `SQLITE_PATH`                | Legacy fallback if `DATABASE_URL` is empty (default `./data/hub.db`). Prefer `DATABASE_URL`. |
| `LOG_DIR`                    | Application log directory (default `./data/logs`).                                                                                                               |
| `LOG_ENABLED`                | Application file log + app logger. Default `true`. `false` / `0` / `no` = off.                                                                                   |
| `LOG_MAX_BYTES`              | Rotate `app.log` when it exceeds this size in bytes. Default `5242880` (5 MiB).                                                                                  |
| `LOG_BACKUP_COUNT`           | How many rotated files to keep (`app.log.1` … `app.log.N`). Default `5`.                                                                                         |
| `COOKIE_SECURE`              | Session cookie `Secure` flag. Default `false` (local HTTP). Set `true` behind HTTPS.                                                                             |

Everything that must survive a restart lives under `./data` (SQLite `hub.db` or `./data/pg` for Compose PostgreSQL, logs, **and uploads** `{DATA_DIR}/uploads/{audio_id}/`). Mount that directory in Docker. The Compose container writes it as uid/gid **1001** (see [Docker Compose](#docker-compose)).

Worker `api_token`s, transcript JSON, summary bodies, and SMTP passwords in the hub database are Fernet-encrypted (AES-128-CBC + HMAC). The key is `SHA-256(HUB_SECRET)`, not the raw secret — same idea as `API_TOKEN` on the workers. The API still returns plaintext to authorized callers. Audio files on disk are **not** encrypted in this version. This only helps if the database leaks without `.env`.

**Changing `HUB_SECRET` makes existing encrypted rows unreadable** (worker tokens, transcripts, summaries, SMTP password). There is no automatic re-encrypt. Set the secret once and keep a backup of `.env`. Same warning the workers give for rotating `API_TOKEN`.

## Attach workers

Compose does **not** start workers. Run **itranscribe-worker** and **isummarize-worker** as their own services, then register them in the hub **Instance** UI (after `/setup`):

1. Start each worker with its own `.env` (`API_TOKEN`, and for summarize also `BASE_URL` / `API_KEY` / `MODEL`).
2. As instance admin: Instance → workers → add a node:
   - `type`: `transcribe` or `summarize`
   - `base_url`: URL the **hub process** can reach (not the browser). Example if the hub is in Docker and the worker is on the host: `http://host.docker.internal:8000`.
   - `api_token`: that worker’s `API_TOKEN`
   - `weight` / `enabled` as needed
3. Hub users never see these fields. The hub copies results into its own DB, then `DELETE`s the worker task.

Do **not** proxy worker `GET /metrics` through the hub. Scrape each worker directly (Bearer `API_TOKEN` on the worker).

## Docker Compose

One image (`idigest-hub:latest`). The Node stage builds `web/dist`; the Python stage serves API + SPA. The process runs as **uid/gid 1001** (not root). Compose mounts `./data:/data`.

By default the hub uses SQLite (`DATABASE_URL=sqlite:////data/hub.db` inside the container). Optional PostgreSQL runs as a second service under profile **`pg`**, with data in `./data/pg` on the host.

### Prepare

1. Copy `.env.example` → `.env` and fill `HUB_SECRET` / `INSTANCE_BOOTSTRAP_TOKEN` / `SESSION_SECRET` (see [`.env`](#env)).
2. Create data dirs if they do not exist (SQLite, logs, uploads). Compose mounts `./data:/data`.

   ```bash
   mkdir -p data/uploads data/logs
   ```

   The container process runs as **uid/gid 1001**. That user must be able to write `./data`.
   If this directory already exists from an older root-owned container, fix ownership once:

   ```bash
   sudo chown -R 1001:1001 ./data
   ```

   Do not chmod `777`. `docker compose down` does not delete `./data`.
3. Compose sets `COOKIE_SECURE=false` for local HTTP. Behind HTTPS set `COOKIE_SECURE=true` in `docker-compose.yml` (or drop that override and set it in `.env`).

### Run (SQLite, default)

```bash
docker compose up --build
```

Add `-d` to run in the background (`docker compose logs -f` for logs). Published port: `8080:8080`. Then open `http://127.0.0.1:8080/setup`.

### Run (PostgreSQL)

In `.env`:

```env
DATABASE_URL=postgresql+psycopg://hub:hub@postgres:5432/hub
POSTGRES_USER=hub
POSTGRES_PASSWORD=hub
POSTGRES_DB=hub
```

Then:

```bash
docker compose --profile pg up --build
```

PostgreSQL stores its files in `./data/pg` (bind mount). Uploads and logs still use `./data/uploads` and `./data/logs`. This is a **separate** database from SQLite — switching back to the default Compose command does not share users or tasks.

If PostgreSQL fails with permission errors on first start, once on the host:

```bash
sudo chown -R 999:999 ./data/pg
```

### Stop

```bash
docker compose down
```

`./data` on the host is not deleted. After switching from a root-owned image, run `sudo chown -R 1001:1001 ./data` before the next `up` if logs show `Permission denied` on `/data`.

## Typical errors

| What you see                                                         | Meaning                                                                                          |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| HTTP **401**, `error.code = bootstrap_invalid`                       | Missing/wrong `INSTANCE_BOOTSTRAP_TOKEN` on `/setup`.                                            |
| HTTP **409**, `error.code = setup_already_done`                      | Instance admin already exists. Use login.                                                        |
| HTTP **403**, `error.code = signup_disabled`                         | Instance admin turned off new orgs, or no non-archived signup tariff.                            |
| Transcripts / worker tokens unreadable after changing `HUB_SECRET`   | Fernet key is `SHA-256` of the previous secret. Restore the old `.env` or re-enter worker tokens and accept lost ciphertext. |
| `Permission denied` on `/data/...` (`hub.db`, `logs`, `uploads`)     | Host `./data` is not writable by uid 1001. Run `sudo chown -R 1001:1001 ./data` and restart. Do not chmod `777`. |
