# Enterprise security brief for auditors

Document for information security audits, due diligence, and compliance reviews.  
**Audience:** internal audit, external auditors, security assessors, procurement security questionnaires.

**Language:** [English](auditor-brief.md) · [Русский](../../ru/compliance/auditor-brief.md)

**Document version:** 1.0 · **Date:** 2026-09-13

---

## Executive summary

**idigest-hub** is an on-premise, multi-tenant control plane for transcription and summarization. It is designed for **private / self-hosted** deployment: source code, CI/CD, container images, database, and user data remain under customer control.

The product implements **defense-in-depth** controls typical of enterprise SaaS platforms, adapted for on-premise operation:

| Strength | What it means for auditors |
| -------- | -------------------------- |
| **Envelope encryption at rest** | Transcripts, summaries, worker tokens, SMTP/SSO secrets in the DB are encrypted with KEK/DEK; a database backup without `.env` does not expose content |
| **Fail-closed cryptography** | Wrong or missing `HUB_SECRET` prevents startup when encrypted data exists — no silent downgrade |
| **Dual key rotation** | Independent KEK rotation (operator) and DEK rotation (instance admin UI) with audited background re-encrypt |
| **Three-tier RBAC + object ACLs** | `instance_admin` / `org_admin` / `org_member` with org boundary, ownership, and in-org sharing |
| **Enterprise SSO** | Per-organization OIDC (Keycloak-compatible), Authorization Code + PKCE (S256), encrypted client secrets, break-glass for admins |
| **Session & API token hygiene** | HttpOnly cookies, hashed tokens (never stored raw), one-time API token display, revocable tokens |
| **Abuse controls** | Configurable rate limits on auth, API, uploads, and task creation; trusted-proxy IP handling |
| **Audit trail** | Persistent `audit_log` for admin actions, impersonation, wallet changes, data wipes, crypto operations |
| **Tenant isolation** | Single-org membership, cross-org access denied by design (covered by automated tests) |
| **Data lifecycle** | User offboarding (transfer/wipe), tariff-driven audio retention purge, personal data export (`GET /me/backup`) |
| **Observability** | Health endpoint, Prometheus metrics (Bearer-protected), Grafana dashboard, readiness gauge |
| **Secure SDLC** | GitLab CI: lint, pytest, frontend build, SAST, dependency scanning, secret detection; non-root container |
| **Operational traceability** | Docker images tagged by commit SHA; manual deploy with GitLab environment audit trail |

This document maps controls to evidence locations. It does **not** claim SOC 2, ISO 27001, HIPAA, or GDPR certification — customers map controls to their frameworks using the tables below.

**Related policy documents:**

- [SECURITY.md](../../../SECURITY.md) — CI/CD policy, vulnerability management, audit checklist
- [Architecture security](../architecture/security.md) — threat model and technical mechanisms
- [Roles and access](../domain/roles-and-access.md) — RBAC matrix

---

## Deployment model and trust boundaries

```
┌─────────────────────────────────────────────────────────────┐
│  Customer private network / VPC                             │
│  ┌──────────────┐   TLS    ┌─────────────┐   localhost     │
│  │ nginx (opt.) │ ───────► │ idigest-hub │ ◄── workers     │
│  └──────────────┘          │  (uid 1001) │     (external)  │
│                            └──────┬──────┘                  │
│                                   │                         │
│              ┌────────────────────┼────────────────────┐    │
│              ▼                    ▼                    ▼    │
│         ./data (DB,            .env (KEK,           S3     │
│          uploads, logs)         session pepper)      (opt.) │
└─────────────────────────────────────────────────────────────┘
```

| Boundary | Customer responsibility | Product responsibility |
| -------- | ----------------------- | ---------------------- |
| Network perimeter, firewall, WAF | Yes | — |
| TLS termination (nginx or hub TLS) | Configure | Provides options |
| `.env` / KEK custody | Yes | Fail-closed if wrong |
| PostgreSQL / SQLite hardening | Yes | ORM, parameterized queries |
| S3 bucket policy & SSE | Yes (if S3 backend) | Sends SSE headers |
| GitLab access control & MR policy | Yes | Documents recommendations |
| Worker security | Yes | Worker tokens encrypted, never exposed to users |

Full matrix: [§ Shared responsibility](#shared-responsibility-matrix).

---

## Control domains and evidence

### 1. Identity and access management (IAM)

| Control | Implementation | Evidence |
| ------- | -------------- | -------- |
| Local password auth | bcrypt hashing, min 8 chars, org password TTL, forced reset | `app/security.py`, `app/routers/auth.py`, [Auth API](../api/auth.md) |
| Session management | HttpOnly `hub_session`, SHA-256 + pepper, sliding TTL | `app/cookies.py`, [Security architecture](../architecture/security.md#session-cookies) |
| API tokens | Prefix `idg_`, shown once, revocable, tariff-gated | `app/routers/auth.py`, tests: `tests/test_auth.py` |
| OIDC SSO | Per-org config, Authorization Code + PKCE (S256), encrypted client secret, HMAC OAuth state, nonce validation | `app/services/sso.py`, tests: `tests/test_sso.py` |
| Break-glass login | `org_admin` + `instance_admin` retain password when SSO enabled | [Security architecture](../architecture/security.md#single-sign-on-sso) |
| RBAC | Three roles + object ownership/shares | [Roles and access](../domain/roles-and-access.md) |
| Impersonation | Instance admin only; admin powers disabled while impersonating; audited | `app/deps.py`, `app/routers/instance.py` |
| Bootstrap gate | One-time `/setup` with `INSTANCE_BOOTSTRAP_TOKEN` | `app/routers/auth.py`, `.env.example` |
| Metrics endpoint | Bearer `METRICS_TOKEN` required | `app/metrics_auth.py`, tests: `tests/test_prometheus.py` |

**Not implemented:** MFA/2FA, OAuth provider mode for third-party apps.

### 2. Data protection and cryptography

| Data class | Protection | Evidence |
| ---------- | ---------- | -------- |
| Transcripts, summaries | Envelope encryption (Fernet + DEK) | `app/crypto.py`, `tests/test_crypto_envelope.py` |
| Worker API tokens | Encrypted in DB; never returned in API | `app/models.py`, [Instance API](../api/instance.md) |
| SMTP / proxy passwords | Encrypted in DB | `ENCRYPTED_COLUMNS` in `app/crypto.py` |
| SSO client secrets | Encrypted in DB | `organizations.sso_client_secret_encrypted` |
| Session / API token raw values | Never stored; SHA-256 + `SESSION_SECRET` | `app/security.py` |
| Passwords | bcrypt | `app/security.py` |
| Audio files (local) | **Not app-encrypted** on disk | Documented; customer encrypts volume or uses S3 |
| Audio files (S3) | Server-side encryption (SSE/SSE-KMS) | `app/services/storage.py`, `STORAGE_BACKEND=s3` |
| In transit | TLS via nginx or hub (`SSL_CERTFILE` / `SSL_KEYFILE`) | `deploy/nginx/idigest-hub.conf.example` |

**Key rotation:**

- **KEK** (`HUB_SECRET`) — operator `.env`; automatic DEK re-wrap on startup; `HUB_SECRET_PREV` for zero-downtime rotation
- **DEK** — instance admin **Security → Encryption**; background re-encrypt job; actions audited

### 3. Application security

| Control | Implementation | Evidence |
| ------- | -------------- | -------- |
| Input validation | Pydantic models on all API endpoints | `app/routers/*`, global handler in `app/main.py` |
| Upload restrictions | Allowed suffixes (`.wav`, `.mp3`, `.m4a`), tariff + global size cap | `app/routers/library.py` |
| SQL injection | SQLAlchemy ORM, parameterized queries | `app/models.py` |
| Path traversal (SPA) | `resolve_spa_path` blocks `..` | `app/main.py`, tests: `tests/test_spa.py` |
| Same-origin architecture | No CORS middleware; SPA + API same origin | [Architecture overview](../architecture/overview.md) |
| Rate limiting | In-memory token buckets: auth, API, uploads, tasks | `app/rate_limit.py`, tests: `tests/test_rate_limit.py` |
| Client IP spoofing | `TRUSTED_PROXIES` — ignore X-Forwarded-For unless trusted | `app/proxy.py`, tests: `tests/test_proxy.py` |
| Security headers | HSTS, CSP, X-Frame-Options via nginx example | `deploy/nginx/idigest-hub.conf.example` |
| Logging hygiene | No secrets or transcript/summary bodies in logs | `app/logging_setup.py`, tests: `tests/test_logging.py` |

### 4. Audit and accountability

Persistent table `audit_log`: `actor_user_id`, optional `on_behalf_of_user_id` (impersonation), `action`, `payload_json`, `created_at`.

**Audited actions (catalog):**

| Action | Trigger |
| ------ | ------- |
| `instance.setup` | First-time instance bootstrap |
| `tariff.create` / `update` / `archive` / `unarchive` | Tariff management |
| `wallet.delta` | Manual wallet credit/debit |
| `org.tariff` / `org.tariff.self` | Org tariff assignment |
| `user.password_reset` | Admin-initiated password reset |
| `user.disable` / `user.enable` | Account suspension |
| `user.offboard.transfer` / `user.offboard.wipe` | User offboarding |
| `impersonate.start` / `impersonate.stop` | Support impersonation |
| `org.sso.update` | SSO configuration change |
| `audio.wipe` / `transcript.wipe` / `transcript.rename` | Data deletion/edit |
| `summary.update` / `summary.delete` | Summary changes |
| `crypto.dek.create` / `crypto.reencrypt.start` / `crypto.reencrypt.cancel` | Encryption key operations |

**Access:** instance admin → **Security → Audit** or `GET /instance/audit` (filters: date, org, user, action).

**Correlated ledgers:** `usage_events` (billing per task), wallet top-ups cross-referenced with `wallet.delta` audit entries.

**Gap (disclosed):** login, logout, failed login, and API token create/revoke are **not** written to `audit_log` (session rows and token table provide partial traceability).

### 5. Multi-tenancy and isolation

| Control | Implementation | Evidence |
| ------- | -------------- | -------- |
| Org as tenant | All artifacts scoped by `org_id` | [Organizations](../domain/organizations.md) |
| One org per user | Unique `memberships.user_id` | `app/models.py` |
| Cross-org isolation | `can_read_object()` enforces org boundary | `app/services/access.py` |
| In-org sharing only | `Share` model within same org | [Roles and access](../domain/roles-and-access.md) |
| Per-org SSO & tariff | Independent OIDC config and billing | `app/models.py` |
| Worker credential isolation | Users never see worker URLs/tokens | [Workers](../operations/workers.md) |

Automated isolation tests: `tests/test_abuse.py`.

### 6. Data lifecycle and privacy

| Capability | Description | Evidence |
| ---------- | ----------- | -------- |
| User offboarding | Transfer artifacts to another user or wipe | `app/services/offboarding.py`, [Organizations](../domain/organizations.md) |
| Audio retention | Tariff-driven purge via background dispatcher | `app/services/retention.py`, [Billing](../domain/billing.md) |
| Personal data export | `GET /me/backup` — ZIP/TGZ of owned artifacts | `app/services/backup.py`, [Library](../domain/library.md) |
| Session/token invalidation | Password change/reset revokes all sessions and API tokens | `app/routers/auth.py` |

### 7. Monitoring and availability

| Control | Implementation | Evidence |
| ------- | -------------- | -------- |
| Liveness | `GET /api/v1/health` | `app/main.py`, Docker healthcheck in `docker-compose.yml` |
| Readiness | `idigest_hub_ready` Prometheus gauge (DB + dispatcher) | `app/prometheus_metrics.py` |
| Metrics | Bearer-protected `GET /metrics` | [Monitoring](../operations/monitoring.md) |
| Dashboard | Grafana JSON import | `grafana/dashboards/idigest-hub.json` |
| Worker health | Hub polls registered workers | `app/services/workers.py` |

### 8. Secure software development lifecycle

| Stage | Control | Evidence |
| ----- | ------- | -------- |
| Lint | `oxlint` on frontend | `.gitlab-ci.yml` → `lint:frontend` |
| Test | Full `pytest` suite (17 test modules including security-focused) | `.gitlab-ci.yml` → `test:backend` |
| Build | TypeScript compile + Vite build | `.gitlab-ci.yml` → `test:frontend` |
| SAST | GitLab `Security/SAST.gitlab-ci.yml` | `.gitlab-ci.yml` |
| Dependency scan | GitLab `Security/Dependency-Scanning.gitlab-ci.yml` | `.gitlab-ci.yml` |
| Secret detection | GitLab `Security/Secret-Detection.gitlab-ci.yml` | `.gitlab-ci.yml`, `.gitignore` |
| Container | Non-root `USER 1001`, slim base images | `Dockerfile` |
| Deploy | Manual only; SHA-tagged images; GitLab environment history | `.gitlab-ci.yml`, [SECURITY.md](../../../SECURITY.md) |

**Security-focused automated tests:**

| Test file | Coverage |
| --------- | -------- |
| `tests/test_auth.py` | Bootstrap, signup, tokens, passwords |
| `tests/test_sso.py` | OIDC flows, SSO/password interaction |
| `tests/test_crypto_envelope.py` | Encryption, KEK rotation, fail-closed startup |
| `tests/test_rate_limit.py` | Rate limiter buckets |
| `tests/test_abuse.py` | Cross-org isolation, privilege boundaries |
| `tests/test_proxy.py` | Trusted proxy IP resolution |
| `tests/test_prometheus.py` | Metrics endpoint auth |
| `tests/test_logging.py` | Log configuration |
| `tests/test_storage.py` | S3/local storage, SSE |

---

## Framework mapping (customer-fillable)

Use this table to map idigest-hub controls to your compliance framework. Status reflects **product capability**; operational evidence is collected by the customer.

| ISO 27001:2022 (Annex A) theme | idigest-hub control | Evidence pointer |
| ------------------------------ | ------------------- | ---------------- |
| A.5 Organizational controls | Shared responsibility documented | This document § Shared responsibility |
| A.8 Asset management | Data classification (encrypted DB fields vs audio blobs) | § Data protection |
| A.9 Access control | RBAC, SSO, session/token model | § IAM, [roles-and-access](../domain/roles-and-access.md) |
| A.10 Cryptography | Envelope encryption, KEK/DEK rotation | § Data protection, [security](../architecture/security.md) |
| A.12 Operations security | Rate limits, logging policy, retention | § Application security, [monitoring](../operations/monitoring.md) |
| A.14 System acquisition / SDLC | CI pipeline, SAST, dependency scan | [SECURITY.md](../../../SECURITY.md) §3 |
| A.16 Incident management | Audit log, metrics, logs | § Audit, [monitoring](../operations/monitoring.md) |
| A.18 Compliance | Audit export, data portability | § Audit, `GET /me/backup` |

| SOC 2 Trust Services Criteria (indicative) | idigest-hub control |
| ------------------------------------------ | ------------------- |
| CC6.1 Logical access | RBAC + SSO + API tokens |
| CC6.2 Credentials | bcrypt, hashed sessions, one-time API tokens |
| CC6.3 Network | Same-origin, TLS deployment patterns |
| CC6.6 Boundary protection | Rate limits, org isolation |
| CC6.7 Transmission | TLS (customer-configured) |
| CC6.8 Malware / changes | CI tests, manual deploy, image SHA tags |
| CC7.2 Monitoring | Prometheus, audit log, health checks |
| C1.1 Confidentiality | Envelope encryption at rest |

---

## Shared responsibility matrix

| Area | Vendor (product) | Customer (operator) |
| ---- | ---------------- | ------------------- |
| Application code & releases | Provides signed-off images via CI | Approves deploy, maintains rollback |
| `.env` secrets (`HUB_SECRET`, etc.) | Documents requirements | Generates, stores, rotates |
| Database encryption at rest | App-level envelope encryption | Disk/volume encryption (optional layer) |
| Audio file encryption | S3 SSE support; local = unencrypted | Choose S3+SSE or encrypted volume |
| TLS certificates | Example nginx config | Procure and renew certs |
| Network firewall / segmentation | — | Configure |
| GitLab security templates | Includes in pipeline | Enable in GitLab Admin |
| SSO IdP | OIDC client integration | Operate Keycloak / IdP |
| Backup & DR (RTO/RPO) | Documents what to back up | Execute backup/restore drills |
| Worker infrastructure | Encrypts stored worker tokens | Secure worker hosts separately |
| Audit log retention | Stores in customer DB | Define retention, export, archival |
| User MFA | — | IdP MFA (SSO) or accept password-only risk |
| SIEM integration | Exports via DB/API/logs | Connect to SIEM |

---

## Known limitations and compensating controls

| Limitation | Risk | Recommended compensating control |
| ---------- | ---- | -------------------------------- |
| No built-in MFA | Credential theft | Enforce MFA at IdP (SSO); VPN for admin access |
| In-memory rate limits, single worker | No horizontal scale; limits reset on restart | nginx rate limiting; single-instance HA acceptance |
| Local audio not app-encrypted | Disk access exposes files | Encrypted volume, S3 backend with SSE-KMS |
| Auth events not in audit_log | Incomplete login forensics | IdP logs, reverse proxy access logs |
| Security headers in nginx only | Weak headers if hub exposed directly | Always deploy behind nginx/TLS proxy |
| No container image CVE scan in CI | Vulnerable base image | Periodic registry scan (Trivy/Grype) |
| No formal certification | Questionnaire gaps | Use this brief + [SECURITY.md](../../../SECURITY.md) as evidence pack |

---

## Audit evidence checklist

| # | Control area | Question | Where to verify |
| - | ------------ | -------- | --------------- |
| 1 | SDLC | Are tests automated on every MR? | GitLab → CI/CD → Pipelines |
| 2 | SDLC | SAST / dependency / secret scans enabled? | MR → Security tab |
| 3 | Supply chain | Image traceable to commit SHA? | Container Registry tags |
| 4 | Deploy | Who deployed and when? | GitLab → Deployments → Environments |
| 5 | Secrets | App secrets excluded from Git? | Secret Detection + `.gitignore` |
| 6 | Runtime | Container non-root? | `Dockerfile` → `USER 1001` |
| 7 | Encryption | DB ciphertext useless without `.env`? | `tests/test_crypto_envelope.py`, restore drill |
| 8 | Access | RBAC enforced cross-org? | `tests/test_abuse.py` |
| 9 | Audit | Admin actions logged? | UI **Security → Audit** or `audit_log` table |
| 10 | SSO | OIDC configured per org? | Org settings, `tests/test_sso.py` |
| 11 | Monitoring | Metrics endpoint protected? | `METRICS_TOKEN`, `tests/test_prometheus.py` |
| 12 | Data lifecycle | Offboarding and export available? | Org admin UI, `GET /me/backup` |
| 13 | Ops | `.env` and `./data` backed up separately? | Customer backup procedure |
| 14 | Network | TLS and security headers in production? | nginx config on deploy host |

Extended CI/CD checklist: [SECURITY.md §8](../../../SECURITY.md#8-audit-checklist).

---

## Related documents

| Document | Purpose |
| -------- | ------- |
| [SECURITY.md](../../../SECURITY.md) | CI/CD policy, vulnerability management |
| [Architecture security](../architecture/security.md) | Technical threat model |
| [Roles and access](../domain/roles-and-access.md) | RBAC matrix |
| [Deployment](../operations/deployment.md) | Production hardening |
| [Monitoring](../operations/monitoring.md) | Alerts and metrics |
| [Database](../operations/database.md) | Schema, encrypted columns |
| [Testing](../development/testing.md) | Running the test suite |

---

*When adding major security controls, update this brief, [SECURITY.md](../../../SECURITY.md), and [architecture/security.md](../architecture/security.md).*
