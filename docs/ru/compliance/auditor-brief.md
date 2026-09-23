# Краткий обзор enterprise-безопасности для аудиторов

Документ для аудита информационной безопасности, due diligence и compliance-оценок.  
**Аудитория:** внутренний аудит, внешние аудиторы, оценщики ИБ, security-опросники при закупках.

**Язык:** [English](../../en/compliance/auditor-brief.md) · [Русский](auditor-brief.md)

**Версия документа:** 1.1 · **Дата:** 2026-09-24

---

## Резюме для руководства

**idigest-hub** — on-premise multi-tenant control plane для транскрибации и суммаризации. Продукт рассчитан на **закрытое / self-hosted** развёртывание: исходный код, CI/CD, образы контейнеров, база данных и пользовательские данные остаются под контролем заказчика.

Продукт реализует **многоуровневую защиту**, характерную для enterprise SaaS, адаптированную под on-premise:

| Сильная сторона | Что это значит для аудиторов |
| --------------- | ---------------------------- |
| **Envelope encryption at rest** | Transcripts, summaries, worker tokens, SMTP/SSO secrets в БД шифруются KEK/DEK; backup БД без `.env` не раскрывает содержимое |
| **Fail-closed криптография** | Неверный или отсутствующий `HUB_SECRET` блокирует старт при наличии зашифрованных данных — без тихого downgrade |
| **Двойная ротация ключей** | Независимая ротация KEK (оператор) и DEK (UI instance admin) с аудируемым фоновым re-encrypt |
| **RBAC из трёх уровней + ACL объектов** | `instance_admin` / `org_admin` / `org_member` с границей org, владением и sharing внутри org |
| **Enterprise SSO** | OIDC per org (Keycloak-compatible), Authorization Code + PKCE (S256), зашифрованные client secrets, break-glass для админов |
| **OAuth 2.1 + MCP** | Опциональные scoped JWT хаба для Open WebUI / MCP tools; гейт org + тариф; PAT на `/mcp` не принимается |
| **Гигиена сессий и API tokens** | HttpOnly cookies, хешированные токены (raw не хранится), одноразовый показ API token, отзыв |
| **Защита от злоупотреблений** | Настраиваемые rate limits на auth, API, upload и создание задач; trusted-proxy для IP |
| **Audit trail** | Персистентный `audit_log` для admin-действий, impersonation, wallet, wipe данных, crypto-операций |
| **Изоляция tenant** | Одна org на пользователя, cross-org доступ запрещён by design (покрыто автотестами) |
| **Жизненный цикл данных** | Offboarding (transfer/wipe), purge audio по тарифу, экспорт персональных данных (`GET /me/backup`) |
| **Observability** | Health endpoint, Prometheus metrics (Bearer), Grafana dashboard, readiness gauge |
| **Secure SDLC** | GitLab CI: lint, pytest, frontend build, SAST, dependency scanning, secret detection; non-root container |
| **Traceability деплоя** | Docker-образы по SHA коммита; manual deploy с audit trail в GitLab Environments |

Документ сопоставляет контроли с точками проверки. **Не заявляет** сертификацию SOC 2, ISO 27001, HIPAA или GDPR — заказчик сопоставляет контроли со своими рамками по таблицам ниже.

**Связанные policy-документы:**

- [SECURITY.ru.md](../../../SECURITY.ru.md) — политика CI/CD, управление уязвимостями, чек-лист аудита
- [Архитектура безопасности](../architecture/security.md) — модель угроз и механизмы
- [Роли и доступ](../domain/roles-and-access.md) — матрица RBAC

---

## Модель развёртывания и границы доверия

```
┌─────────────────────────────────────────────────────────────┐
│  Закрытая сеть / VPC заказчика                              │
│  ┌──────────────┐   TLS    ┌─────────────┐   localhost     │
│  │ nginx (opt.) │ ───────► │ idigest-hub │ ◄── workers     │
│  └──────────────┘          │  (uid 1001) │     (внешние)   │
│                            └──────┬──────┘                  │
│                                   │                         │
│              ┌────────────────────┼────────────────────┐    │
│              ▼                    ▼                    ▼    │
│         ./data (БД,            .env (KEK,           S3     │
│          uploads, logs)         session pepper)      (opt.) │
└─────────────────────────────────────────────────────────────┘
```

| Граница | Ответственность заказчика | Ответственность продукта |
| ------- | ------------------------- | ------------------------ |
| Периметр сети, firewall, WAF | Да | — |
| TLS termination (nginx или hub TLS) | Настроить | Предоставляет варианты |
| `.env` / custody KEK | Да | Fail-closed при ошибке |
| Hardening PostgreSQL / SQLite | Да | ORM, parameterized queries |
| S3 bucket policy & SSE | Да (при S3 backend) | Отправляет SSE headers |
| GitLab access control & MR policy | Да | Документирует рекомендации |
| Безопасность workers | Да | Worker tokens зашифрованы, не отдаются пользователям |

Полная матрица: [§ Матрица shared responsibility](#матрица-shared-responsibility).

---

## Домены контроля и доказательства

### 1. Управление идентификацией и доступом (IAM)

| Контроль | Реализация | Доказательство |
| -------- | ---------- | -------------- |
| Локальный password auth | bcrypt, min 8 chars, org password TTL, forced reset | `app/security.py`, `app/routers/auth.py`, [Auth API](../api/auth.md) |
| Управление сессиями | HttpOnly `hub_session`, SHA-256 + pepper, sliding TTL | `app/cookies.py`, [Безопасность](../architecture/security.md#session-cookies) |
| API tokens | Prefix `idg_`, показ один раз, отзыв, tariff-gated | `app/routers/auth.py`, tests: `tests/test_auth.py` |
| OIDC SSO | Per-org config, Authorization Code + PKCE (S256), encrypted client secret, HMAC OAuth state, nonce validation | `app/services/sso.py`, tests: `tests/test_sso.py` |
| OAuth 2.1 + MCP | Опциональный authorization server хаба + Streamable HTTP `/mcp`; PKCE S256, DCR, scoped JWT tools; нужен org member + `api_enabled` | `app/services/oauth_provider.py`, `app/services/mcp_integration.py`, [MCP API](../api/mcp.md), tests: `tests/test_oauth_provider.py`, `tests/test_mcp_library.py` |
| TOTP 2FA | Login challenge, org `mfa_required`, recovery codes, token step-up, encrypted secret | `app/services/mfa.py`, `app/services/totp.py`, tests: `tests/test_mfa.py` |
| Break-glass login | `org_admin` + `instance_admin` сохраняют password при SSO | [Безопасность](../architecture/security.md#single-sign-on-sso) |
| RBAC | Три роли + ownership/shares | [Роли и доступ](../domain/roles-and-access.md) |
| Impersonation | Только instance admin; admin powers отключены при impersonation; аудит | `app/deps.py`, `app/routers/instance.py` |
| Bootstrap gate | Одноразовый `/setup` с `INSTANCE_BOOTSTRAP_TOKEN` | `app/routers/auth.py`, `.env.example` |
| Metrics endpoint | Bearer `METRICS_TOKEN` обязателен | `app/metrics_auth.py`, tests: `tests/test_prometheus.py` |

**MFA локальных пользователей:** TOTP 2FA (opt-in в профиле; org может требовать при выключенном SSO). SSO — MFA на IdP.

**OAuth provider:** включается через `OAUTH_PROVIDER_ENABLED`. Сторонние MCP-клиенты (например Open WebUI) регистрируются через DCR, получают JWT с scope и вызывают tools библиотеки на `/mcp`. Instance admin без членства в org не может пройти OAuth.

### 2. Защита данных и криптография

| Класс данных | Защита | Доказательство |
| ------------ | ------ | -------------- |
| Transcripts, summaries | Envelope encryption (Fernet + DEK) | `app/crypto.py`, `tests/test_crypto_envelope.py` |
| Worker API tokens | Зашифрованы в БД; не возвращаются в API | `app/models.py`, [Instance API](../api/instance.md) |
| SMTP / proxy passwords | Зашифрованы в БД | `ENCRYPTED_COLUMNS` в `app/crypto.py` |
| SSO client secrets | Зашифрованы в БД | `organizations.sso_client_secret_encrypted` |
| Raw session / API token | Не хранится; SHA-256 + `SESSION_SECRET` | `app/security.py` |
| Passwords | bcrypt | `app/security.py` |
| Audio files (local) | **Не шифруются** приложением на диске | Документировано; encrypted volume или S3 |
| Audio files (S3) | Server-side encryption (SSE/SSE-KMS) | `app/services/storage.py`, `STORAGE_BACKEND=s3` |
| In transit | TLS через nginx или hub | `deploy/nginx/idigest-hub.conf.example` |

**Ротация ключей:**

- **KEK** (`HUB_SECRET`) — `.env` оператора; автоматическая переобёртка DEK при старте; `HUB_SECRET_PREV`
- **DEK** — instance admin **Security → Encryption**; фоновый re-encrypt; действия в audit log

### 3. Безопасность приложения

| Контроль | Реализация | Доказательство |
| -------- | ---------- | -------------- |
| Валидация входа | Pydantic models на всех API endpoints | `app/routers/*`, handler в `app/main.py` |
| Ограничения upload | Suffixes (`.wav`, `.mp3`, `.m4a`), tariff + global size cap | `app/routers/library.py` |
| SQL injection | SQLAlchemy ORM | `app/models.py` |
| Path traversal (SPA) | `resolve_spa_path` блокирует `..` | `app/main.py`, tests: `tests/test_spa.py` |
| Same-origin architecture | Без CORS; SPA + API same origin | [Обзор архитектуры](../architecture/overview.md) |
| Rate limiting | In-memory token buckets | `app/rate_limit.py`, tests: `tests/test_rate_limit.py` |
| Client IP spoofing | `TRUSTED_PROXIES` | `app/proxy.py`, tests: `tests/test_proxy.py` |
| Security headers | HSTS, CSP, X-Frame-Options в nginx example | `deploy/nginx/idigest-hub.conf.example` |
| Гигиена логов | Без секретов и transcript/summary bodies | `app/logging_setup.py`, tests: `tests/test_logging.py` |

### 4. Аудит и подотчётность

Таблица `audit_log`: `actor_user_id`, опционально `on_behalf_of_user_id` (impersonation), `action`, `payload_json`, `created_at`.

**Каталог аудируемых действий:**

| Action | Триггер |
| ------ | ------- |
| `instance.setup` | Первичный bootstrap инстанса |
| `tariff.create` / `update` / `archive` / `unarchive` | Управление тарифами |
| `wallet.delta` | Ручное изменение wallet |
| `org.create` / `org.delete` | Provisioning / каскадное удаление org instance admin |
| `org.tariff` / `org.tariff.self` | Назначение тарифа org |
| `org.public_links_policy` | Разрешение/запрет public summary links |
| `user.password_reset` | Admin-initiated password reset |
| `user.disable` / `user.enable` | Блокировка аккаунта |
| `user.offboard.transfer` / `user.offboard.wipe` | Offboarding пользователя |
| `impersonate.start` / `impersonate.stop` | Support impersonation |
| `org.sso.update` | Изменение SSO config |
| `audio.wipe` / `transcript.wipe` / `transcript.rename` | Удаление/редактирование данных |
| `summary.update` / `summary.delete` | Изменения summary |
| `summary.public_link.create` / `summary.public_link.revoke` / `summary.public_link.view` | Гостевые public links |
| `crypto.dek.create` / `crypto.reencrypt.start` / `crypto.reencrypt.cancel` | Операции с ключами шифрования |

**Доступ:** instance admin → **Security → Audit** или `GET /instance/audit` (фильтры; пагинация; CSV через `/instance/audit/export`).

**Связанные ledger:** `usage_events` (billing), wallet top-ups ↔ `wallet.delta`.

**Gap (раскрыт):** login, logout, failed login и create/revoke API token **не** пишутся в `audit_log`.

### 5. Multi-tenancy и изоляция

| Контроль | Реализация | Доказательство |
| -------- | ---------- | -------------- |
| Org как tenant | Все артефакты по `org_id` | [Организации](../domain/organizations.md) |
| Одна org на пользователя | Unique `memberships.user_id` | `app/models.py` |
| Cross-org isolation | `can_read_object()` | `app/services/access.py` |
| Sharing только внутри org | Модель `Share` | [Роли и доступ](../domain/roles-and-access.md) |
| Per-org SSO & tariff | Независимый OIDC и billing | `app/models.py` |
| Изоляция worker credentials | Пользователи не видят worker URLs/tokens | [Воркеры](../operations/workers.md) |

Автотесты изоляции: `tests/test_abuse.py`.

### 6. Жизненный цикл данных и privacy

| Возможность | Описание | Доказательство |
| ----------- | -------- | -------------- |
| User offboarding | Transfer или wipe артефактов | `app/services/offboarding.py` |
| Audio retention | Purge по тарифу через dispatcher | `app/services/retention.py` |
| Экспорт персональных данных | `GET /me/backup` — ZIP/TGZ | `app/services/backup.py` |
| Инвалидация session/token | Password change/reset отзывает все sessions и API tokens | `app/routers/auth.py` |

### 7. Мониторинг и доступность

| Контроль | Реализация | Доказательство |
| -------- | ---------- | -------------- |
| Liveness | `GET /api/v1/health` | `app/main.py`, Docker healthcheck |
| Readiness | `idigest_hub_ready` gauge | `app/prometheus_metrics.py` |
| Metrics | Bearer-protected `GET /metrics` | [Мониторинг](../operations/monitoring.md) |
| Dashboard | Grafana JSON import | `grafana/dashboards/idigest-hub.json` |
| Worker health | Hub polls workers | `app/services/workers.py` |

### 8. Secure SDLC

| Стадия | Контроль | Доказательство |
| ------ | -------- | -------------- |
| Lint | `oxlint` frontend | `.gitlab-ci.yml` |
| Test | `pytest` (17 модулей, включая security) | `.gitlab-ci.yml` |
| Build | TypeScript + Vite | `.gitlab-ci.yml` |
| SAST | GitLab SAST template | `.gitlab-ci.yml` |
| Dependency scan | GitLab Dependency Scanning | `.gitlab-ci.yml` |
| Secret detection | GitLab Secret Detection | `.gitlab-ci.yml` |
| Container | Non-root `USER 1001` | `Dockerfile` |
| Deploy | Manual; SHA tags; GitLab Environments | [SECURITY.ru.md](../../../SECURITY.ru.md) |

**Security-focused автотесты:** `test_auth`, `test_mfa`, `test_sso`, `test_crypto_envelope`, `test_rate_limit`, `test_abuse`, `test_proxy`, `test_prometheus`, `test_logging`, `test_storage`.

---

## Сопоставление с фреймворками (заполняет заказчик)

| ISO 27001:2022 (Annex A) | Контроль idigest-hub | Указатель |
| ------------------------ | -------------------- | --------- |
| A.5 Организационные | Shared responsibility | § Матрица shared responsibility |
| A.8 Управление активами | Классификация данных | § Защита данных |
| A.9 Контроль доступа | RBAC, SSO, sessions/tokens | § IAM |
| A.10 Криптография | Envelope encryption, ротация | § Защита данных |
| A.12 Операционная безопасность | Rate limits, logging, retention | § Безопасность приложения |
| A.14 SDLC | CI, SAST, dependency scan | [SECURITY.ru.md](../../../SECURITY.ru.md) |
| A.16 Инциденты | Audit log, metrics, logs | § Аудит |
| A.18 Compliance | Audit export, portability | § Аудит, `GET /me/backup` |

| SOC 2 TSC (ориентир) | Контроль idigest-hub |
| -------------------- | -------------------- |
| CC6.1 Logical access | RBAC + SSO + API tokens |
| CC6.2 Credentials | bcrypt, hashed sessions, one-time API tokens |
| CC6.3 Network | Same-origin, TLS patterns |
| CC6.6 Boundary | Rate limits, org isolation |
| CC6.7 Transmission | TLS (настраивает заказчик) |
| CC6.8 Changes | CI tests, manual deploy, SHA tags |
| CC7.2 Monitoring | Prometheus, audit log, health |
| C1.1 Confidentiality | Envelope encryption at rest |

---

## Матрица shared responsibility

| Область | Вендор (продукт) | Заказчик (оператор) |
| ------- | ---------------- | ------------------- |
| Код и релизы | CI-образы | Approve deploy, rollback |
| `.env` secrets | Документирует требования | Генерирует, хранит, ротирует |
| Шифрование БД at rest | App-level envelope | Disk encryption (опционально) |
| Шифрование audio | S3 SSE; local = без app-encrypt | S3+SSE или encrypted volume |
| TLS certificates | nginx example | Закупка и renewal |
| Firewall / segmentation | — | Настройка |
| GitLab security templates | В pipeline | Enable в GitLab Admin |
| SSO IdP | OIDC integration | Keycloak / IdP |
| Backup & DR | Документирует что бэкапить | Drills, RTO/RPO |
| Workers | Шифрует tokens в БД | Hardening worker hosts |
| Retention audit log | Хранит в БД заказчика | Retention, export, SIEM |
| MFA | TOTP для local users; org policy без SSO | IdP MFA для SSO members |
| SIEM | DB/API/logs | Подключение |

---

## Известные ограничения и компенсирующие меры

| Ограничение | Риск | Компенсирующая мера |
| ----------- | ---- | ------------------- |
| Local users без 2FA | Кража credentials | TOTP в профиле; org `mfa_required`; IdP MFA для SSO |
| In-memory rate limits, single worker | Нет horizontal scale | nginx rate limiting |
| Local audio без app-encrypt | Доступ к диску | Encrypted volume, S3+SSE-KMS |
| Auth events не в audit_log | Неполная forensics login | IdP logs, proxy access logs |
| Security headers только в nginx | Слабые headers при прямом доступе | Deploy за nginx/TLS proxy |
| Нет container CVE scan в CI | Уязвимый base image | Trivy/Grype на registry |
| Нет формальной сертификации | Gaps в опросниках | Этот brief + [SECURITY.ru.md](../../../SECURITY.ru.md) |

---

## Чек-лист доказательств для аудита

| # | Область | Вопрос | Где проверить |
| - | ------- | ------ | ------------- |
| 1 | SDLC | Автотесты на каждом MR? | GitLab → CI/CD |
| 2 | SDLC | SAST / dependency / secret scans? | MR → Security |
| 3 | Supply chain | Образ → SHA коммита? | Container Registry |
| 4 | Deploy | Кто и когда деплоил? | GitLab → Deployments |
| 5 | Secrets | Секреты не в Git? | Secret Detection |
| 6 | Runtime | Non-root container? | `Dockerfile` |
| 7 | Encryption | Ciphertext бесполезен без `.env`? | `test_crypto_envelope`, restore drill |
| 8 | Access | RBAC cross-org? | `test_abuse` |
| 9 | Audit | Admin actions logged? | **Security → Audit** |
| 10 | SSO | OIDC per org? | Org settings, `test_sso` |
| 11 | Monitoring | Metrics protected? | `METRICS_TOKEN` |
| 12 | Data lifecycle | Offboarding и export? | `GET /me/backup` |
| 13 | Ops | `.env` и `./data` бэкапятся отдельно? | Процедура заказчика |
| 14 | Network | TLS и security headers? | nginx на deploy host |

Расширенный CI/CD чек-лист: [SECURITY.ru.md §8](../../../SECURITY.ru.md#8-чек-лист-для-аудита).

---

## Связанные документы

| Документ | Назначение |
| -------- | ---------- |
| [SECURITY.ru.md](../../../SECURITY.ru.md) | CI/CD, vulnerability management |
| [Архитектура безопасности](../architecture/security.md) | Модель угроз |
| [Роли и доступ](../domain/roles-and-access.md) | RBAC |
| [Деплой](../operations/deployment.md) | Production hardening |
| [Мониторинг](../operations/monitoring.md) | Alerts и metrics |
| [База данных](../operations/database.md) | Schema, encrypted columns |
| [Тесты](../development/testing.md) | Запуск test suite |

---

*При добавлении major security controls обновляйте этот brief, [SECURITY.ru.md](../../../SECURITY.ru.md) и [architecture/security.md](../architecture/security.md).*
