# Security and CI/CD policy (idigest-hub)

Document for auditors, information security teams, and operators.  
Application threat model and protection mechanisms: [docs/en/architecture/security.md](docs/en/architecture/security.md) (EN) · [docs/ru/architecture/security.md](docs/ru/architecture/security.md) (RU).

**Language:** [English](SECURITY.md) · [Русский](SECURITY.ru.md)

**Document version:** 1.0 · **Date:** 2026-09-10

---

## 1. Purpose and context

**idigest-hub** is an on-premise control plane for transcription and summarization. It is deployed in a **private environment** (self-hosted GitLab, Docker Compose on the customer server). Source code, pipelines, and images stay within the organization’s infrastructure unless agreed otherwise.

| Aspect | Implementation |
| ------ | -------------- |
| Repository | Self-hosted GitLab |
| Build | GitLab CI/CD (`.gitlab-ci.yml`) |
| Artifacts | GitLab Container Registry (image tagged by commit SHA) |
| Deploy (current) | Docker Compose on the target host |
| Deploy (planned) | Kubernetes — separate pipeline job, enabled via `K8S_DEPLOY_ENABLED` |

---

## 2. Source control

Recommended GitLab project settings (configured by the GitLab administrator, not in the repository):

| Control | Purpose |
| ------- | ------- |
| Protected branches (`main` / `master`) | No direct push; changes only via Merge Request |
| “Pipelines must succeed” | MR cannot merge when CI fails |
| Minimum approvers ≥ 1 | Separation of duties (development / review) |
| Protected tags | Release tags created by maintainers only |
| Signed commits (optional) | Additional commit authorship verification |

Application secrets (`HUB_SECRET`, `SESSION_SECRET`, `INSTANCE_BOOTSTRAP_TOKEN`, DB passwords) are **not stored in Git**. `.env` is in `.gitignore`. On the deploy server, `.env` is created and maintained by operators outside CI.

---

## 3. CI/CD pipeline

Stage flow (see [`.gitlab-ci.yml`](.gitlab-ci.yml)):

```
lint → test (+ SAST / dependency / secret scans) → build → deploy
```

### 3.1 Lint

| Job | Checks |
| --- | ------ |
| `lint:frontend` | `oxlint` in `web/` |

No backend linter in CI; backend quality is enforced by `pytest` automation.

### 3.2 Test

| Job | Checks |
| --- | ------ |
| `test:backend` | `pytest` — API, auth, billing, rate limits, etc. (`tests/`) |
| `test:frontend` | `npm run build` — TypeScript and SPA build |

Backend tests use isolated SQLite in `tmp_path`; external workers are not required.

### 3.3 Security (GitLab templates)

Official templates are included (must be enabled in **Admin → Security & Compliance** on self-hosted GitLab):

| Template | Purpose |
| -------- | ------- |
| `Security/SAST.gitlab-ci.yml` | Static analysis of source code |
| `Security/Dependency-Scanning.gitlab-ci.yml` | Known vulnerabilities in dependencies (Python, npm) |
| `Security/Secret-Detection.gitlab-ci.yml` | Accidentally committed secrets |

Reports are available in MR → **Security** and retained in GitLab for audit.

### 3.4 Build

| Job | Behavior |
| --- | -------- |
| `build:docker` | Build image from [`Dockerfile`](Dockerfile), push to GitLab Container Registry |

Image tags:

- `$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA` — **canonical** (traceability: commit → image)
- `$CI_REGISTRY_IMAGE:latest` — default branch only

The container runs as **uid/gid 1001** (non-root).

### 3.5 Deploy

| Job | Environment | Trigger |
| --- | ----------- | ------- |
| `deploy:compose:staging` | `staging` | Manual, default branch |
| `deploy:compose:production` | `production` | Manual, default branch or tag |
| `deploy:kubernetes` | `production` | Manual, only when `K8S_DEPLOY_ENABLED=true` |

Deploy is **always manual** (`when: manual`) — GitLab records who triggered deploy and when, linked to the commit SHA.

#### Docker Compose (current)

1. Job connects to the host via SSH (`DEPLOY_HOST`).
2. Copies current `docker-compose.yml` and [`deploy/compose-deploy.sh`](deploy/compose-deploy.sh) from the repository.
3. Logs in to the registry → `docker compose pull` → `docker compose up -d`.
4. The server must already have the deploy directory (`DEPLOY_PATH`), `./data`, and a local `.env` (not from Git).

Rollback: re-run manual deploy with the previous `$CI_COMMIT_SHA`, or `docker compose up -d` with the previous image tag.

#### Kubernetes (planned)

Job `deploy:kubernetes` is reserved. After manifests exist in `deploy/k8s/`:

1. Set `K8S_DEPLOY_ENABLED=true` in CI/CD Variables.
2. Provide `KUBE_CONFIG` (base64) or use the GitLab Kubernetes agent.
3. The job runs `kubectl set image` / `kubectl rollout status`.

---

## 4. CI/CD secrets

| Variable | Used for | Recommendations |
| -------- | -------- | --------------- |
| `CI_REGISTRY_USER`, `CI_REGISTRY_PASSWORD` | Build / deploy | Provided by GitLab; mask on deploy |
| `SSH_PRIVATE_KEY` | SSH deploy | Masked, Protected, protected branches only |
| `SSH_KNOWN_HOSTS` | SSH deploy | Target host fingerprint |
| `STAGING_DEPLOY_HOST`, `STAGING_DEPLOY_USER`, `STAGING_DEPLOY_PATH`, `STAGING_URL` | Staging deploy | Protected |
| `PRODUCTION_DEPLOY_HOST`, `PRODUCTION_DEPLOY_USER`, `PRODUCTION_DEPLOY_PATH`, `PRODUCTION_URL` | Production deploy | Protected |
| `COMPOSE_PROFILES` | Deploy (optional) | `pg` for PostgreSQL profile |
| `K8S_DEPLOY_ENABLED`, `KUBE_CONFIG`, `K8S_NAMESPACE` | K8s (future) | Masked, Protected |

**Application** secrets (`HUB_SECRET`, etc.) are **not passed through CI** — they live only in `.env` on the server.

---

## 5. Application security (summary)

Full description: [docs/en/architecture/security.md](docs/en/architecture/security.md).

| Area | Measure |
| ---- | ------- |
| Database data | Fernet encryption of sensitive fields (`HUB_SECRET`) |
| Sessions | HttpOnly cookie, token hash with `SESSION_SECRET` |
| API tokens | Shown once; rate limits |
| SSO | OIDC per org; client secret encrypted |
| Workers | Worker tokens are not exposed to end users |
| Action audit | `audit_log` table (setup, wallet, impersonation, …) |
| Rate limiting | In-memory, single Uvicorn process (`--workers 1`) |
| Audio files | **Not encrypted** on disk in the current version |

---

## 6. Operations and backup

| Data | Location | Backup |
| ---- | -------- | ------ |
| SQLite / PostgreSQL | `./data` on host | Copy `./data` + **separately** `.env` |
| Audio uploads | `./data/uploads/` | Together with `./data` |
| Logs | `./data/logs/` | Per customer policy |

Changing `HUB_SECRET` without a backup makes encrypted DB rows unreadable. Changing `SESSION_SECRET` logs out all users.

---

## 7. Vulnerability management

1. **Dependency Scanning** and **SAST** on every pipeline for protected branches.
2. Critical findings → GitLab Issues; remediation timeline per customer policy.
3. Base image updates (`python:3.12-slim`, `node:22-alpine`) on CI rebuild.

To report a product vulnerability: contact the maintainer / instance admin of the repository owner (on-premise — internal security channel).

---

## 8. Audit checklist

| # | Question | Where to verify |
| - | -------- | --------------- |
| 1 | Are automated tests run on MR? | GitLab → CI/CD → Pipelines |
| 2 | Is merge blocked without a green pipeline? | Settings → Merge requests |
| 3 | Are SAST / dependency scans present? | MR → Security tab |
| 4 | Is the image tied to commit SHA? | Container Registry → tags |
| 5 | Who deployed and when? | Deployments → Environments |
| 6 | Are secrets excluded from Git? | Secret Detection + `.gitignore` |
| 7 | Does the app run non-root in the container? | `Dockerfile` → `USER 1001` |
| 8 | Is there an in-app audit log? | DB → `audit_log` |
| 9 | Is there a rollback procedure? | §3.5 — redeploy previous SHA |
| 10 | Is server `.env` under ops control? | Deploy server, outside the repository |

---

## 9. Related documents

- [Deployment (EN)](docs/en/operations/deployment.md)
- [Testing (EN)](docs/en/development/testing.md)
- [README — Docker Compose](README.md#docker-compose)

---

*When changing the pipeline or deployment model, update this document and the version in the header.*
