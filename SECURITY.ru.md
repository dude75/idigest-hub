# Политика безопасности и CI/CD (idigest-hub)

Документ для аудиторов, службы информационной безопасности и операторов.  
Технические детали модели угроз и механизмов защиты приложения: [docs/ru/architecture/security.md](docs/ru/architecture/security.md) (RU) · [docs/en/architecture/security.md](docs/en/architecture/security.md) (EN).

**Язык:** [English](SECURITY.md) · [Русский](SECURITY.ru.md)

**Версия документа:** 1.0 · **Дата:** 2026-09-10

---

## 1. Назначение и контекст

**idigest-hub** — on-premise control plane для транскрибации и суммаризации. Развёртывание выполняется в **закрытом контуре** (self-hosted GitLab, Docker Compose на сервере заказчика). Исходный код, пайплайны и образы не покидают инфраструктуру организации, если иное не согласовано отдельно.

| Аспект | Реализация |
| ------ | ---------- |
| Репозиторий | Self-hosted GitLab |
| Сборка | GitLab CI/CD (`.gitlab-ci.yml`) |
| Артефакты | Container Registry GitLab (образ по SHA коммита) |
| Деплой (текущий) | Docker Compose на целевом хосте |
| Деплой (план) | Kubernetes — отдельный job в пайплайне, включается переменной `K8S_DEPLOY_ENABLED` |

---

## 2. Контроль исходного кода

Рекомендуемые настройки проекта в GitLab (фиксируются администратором GitLab, не в репозитории):

| Контроль | Назначение |
| -------- | ---------- |
| Protected branches (`main` / `master`) | Запрет прямого push; изменения только через Merge Request |
| «Pipelines must succeed» | MR нельзя смержить при падении CI |
| Minimum approvers ≥ 1 | Разделение обязанностей (разработка / ревью) |
| Protected tags | Релизные теги создают только maintainer |
| Signed commits (опционально) | Дополнительная проверка авторства коммитов |

Секреты приложения (`HUB_SECRET`, `SESSION_SECRET`, `INSTANCE_BOOTSTRAP_TOKEN`, пароли БД) **не хранятся в Git**. Файл `.env` в `.gitignore`. На сервере деплоя `.env` создаётся и обслуживается оператором вне CI.

---

## 3. CI/CD pipeline

Схема стадий (файл [`.gitlab-ci.yml`](.gitlab-ci.yml)):

```
lint → test (+ SAST / dependency / secret scans) → build → deploy
```

### 3.1 Lint

| Job | Что проверяет |
| --- | ------------- |
| `lint:frontend` | `oxlint` в каталоге `web/` |

Backend-линтер в CI не включён; качество backend обеспечивается автотестами `pytest`.

### 3.2 Test

| Job | Что проверяет |
| --- | ------------- |
| `test:backend` | `pytest` — API, auth, billing, rate limits и др. (`tests/`) |
| `test:frontend` | `npm run build` — TypeScript и сборка SPA |

Тесты backend используют изолированный SQLite в `tmp_path`; внешние workers не требуются.

### 3.3 Security (шаблоны GitLab)

Подключаются официальные шаблоны (требуют включения в **Admin → Security & Compliance** на self-hosted GitLab):

| Шаблон | Назначение |
| ------ | ---------- |
| `Security/SAST.gitlab-ci.yml` | Статический анализ исходного кода |
| `Security/Dependency-Scanning.gitlab-ci.yml` | Известные уязвимости в зависимостях (Python, npm) |
| `Security/Secret-Detection.gitlab-ci.yml` | Поиск случайно закоммиченных секретов |

Отчёты доступны в MR → **Security** и хранятся в GitLab для аудита.

### 3.4 Build

| Job | Поведение |
| --- | --------- |
| `build:docker` | Сборка образа по [`Dockerfile`](Dockerfile), push в GitLab Container Registry |

Теги образа:

- `$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA` — **канонический** (traceability: commit → образ)
- `$CI_REGISTRY_IMAGE:latest` — только для ветки по умолчанию

Образ работает от **uid/gid 1001** (non-root).

### 3.5 Deploy

| Job | Окружение | Триггер |
| --- | --------- | ------- |
| `deploy:compose:staging` | `staging` | Manual, ветка по умолчанию |
| `deploy:compose:production` | `production` | Manual, ветка по умолчанию или tag |
| `deploy:kubernetes` | `production` | Manual, только если `K8S_DEPLOY_ENABLED=true` |

Деплой **всегда ручной** (`when: manual`) — в GitLab фиксируется, кто и когда нажал deploy, с привязкой к SHA.

#### Docker Compose (текущий)

1. Job подключается по SSH к хосту (`DEPLOY_HOST`).
2. Копирует актуальные `docker-compose.yml` и [`deploy/compose-deploy.sh`](deploy/compose-deploy.sh) из репозитория.
3. Выполняет login в registry → `docker compose pull` → `docker compose up -d`.
4. На сервере заранее подготовлены каталог деплоя (`DEPLOY_PATH`), `./data`, локальный `.env` (не из Git).

Откат: повторный manual deploy с предыдущим `$CI_COMMIT_SHA` или `docker compose up -d` с прежним тегом образа.

#### Kubernetes (план)

Job `deploy:kubernetes` зарезервирован. После появления манифestов в `deploy/k8s/`:

1. Установить `K8S_DEPLOY_ENABLED=true` в CI/CD Variables.
2. Задать `KUBE_CONFIG` (base64) или использовать GitLab Kubernetes agent.
3. Job выполнит `kubectl set image` / `kubectl rollout status`.

---

## 4. Секреты в CI/CD

| Переменная | Где используется | Рекомендации |
| ---------- | ---------------- | ------------ |
| `CI_REGISTRY_USER`, `CI_REGISTRY_PASSWORD` | Build / deploy | Автоматически от GitLab; deploy — masked |
| `SSH_PRIVATE_KEY` | Deploy по SSH | Masked, Protected, только protected branches |
| `SSH_KNOWN_HOSTS` | Deploy по SSH | Fingerprint целевого хоста |
| `STAGING_DEPLOY_HOST`, `STAGING_DEPLOY_USER`, `STAGING_DEPLOY_PATH`, `STAGING_URL` | Staging deploy | Protected |
| `PRODUCTION_DEPLOY_HOST`, `PRODUCTION_DEPLOY_USER`, `PRODUCTION_DEPLOY_PATH`, `PRODUCTION_URL` | Production deploy | Protected |
| `COMPOSE_PROFILES` | Deploy (опционально) | `pg` для PostgreSQL profile |
| `K8S_DEPLOY_ENABLED`, `KUBE_CONFIG`, `K8S_NAMESPACE` | K8s (будущее) | Masked, Protected |

Секреты **приложения** (`HUB_SECRET` и т.д.) в CI **не передаются** — только на сервере в `.env`.

---

## 5. Безопасность приложения (кратко)

Полное описание: [docs/ru/architecture/security.md](docs/ru/architecture/security.md).

| Область | Мера |
| ------- | ---- |
| Данные в БД | Envelope encryption: DEK + KEK (`HUB_SECRET`); ротация DEK — Security → Encryption |
| Сессии | HttpOnly cookie, hash токена с `SESSION_SECRET` |
| API tokens | Показ один раз; rate limits |
| SSO | OIDC per org; client secret зашифрован |
| Workers | Токены workers не отдаются пользователям |
| Аудит действий | Таблица `audit_log` (setup, wallet, impersonation, …) |
| Rate limiting | In-memory, один процесс Uvicorn (`--workers 1`) |
| Файлы audio | Local: **не** шифруются приложением. S3: **SSE** на object storage (`STORAGE_BACKEND=s3`) |

---

## 6. Эксплуатация и резервное копирование

| Данные | Расположение | Backup |
| ------ | ------------ | ------ |
| SQLite / PostgreSQL | `./data` на хосте | Копия каталога `./data` + **отдельно** `.env` |
| Загрузки audio | `./data/uploads/` (local) или S3 bucket (`STORAGE_BACKEND=s3`) | Local: с `./data`. S3: backup/replication bucket у провайдера |
| Логи | `./data/logs/` | По политике заказчика |

**Ротация KEK:** новый `HUB_SECRET`, `HUB_SECRET_PREV` = старый, рестарт — переобёртка DEK при старте (держите оба до завершения). **Ротация DEK:** UI instance admin (фоновый re-encrypt). Неверный/пустой `HUB_SECRET` при наличии данных блокирует старт. Смена `SESSION_SECRET` разлогинивает всех.

---

## 7. Управление уязвимостями

1. **Dependency Scanning** и **SAST** в каждом пайплайне на protected branches.
2. Критичные findings — задачи в GitLab Issues, срок устранения по политике заказчика.
3. Обновления базового образа (`python:3.12-slim`, `node:22-alpine`) — при rebuild в CI.

Сообщить о уязвимости в продукте: контакт maintainer / instance admin организации-владельца репозитория (on-premise — внутренний канал ИБ).

---

## 8. Чек-лист для аудита

| # | Вопрос | Где подтвердить |
| - | ------ | ---------------- |
| 1 | Есть ли автоматические тесты на MR? | GitLab → CI/CD → Pipelines |
| 2 | Блокируется ли merge без green pipeline? | Settings → Merge requests |
| 3 | Есть ли SAST / dependency scan? | MR → Security tab |
| 4 | Образ привязан к SHA коммита? | Container Registry → tags |
| 5 | Кто деплоил и когда? | Deployments → Environments |
| 6 | Секреты не в Git? | Secret Detection + `.gitignore` |
| 7 | Приложение не root в контейнере? | `Dockerfile` → `USER 1001` |
| 8 | Есть ли audit log в приложении? | БД → `audit_log` |
| 9 | Есть ли процедура отката? | §3.5 — redeploy предыдущего SHA |
| 10 | `.env` на сервере под контролем ops? | Сервер деплоя, вне репозитория |

---

## 9. Связанные документы

- [Развёртывание (RU)](docs/ru/operations/deployment.md)
- [Тестирование (RU)](docs/ru/development/testing.md)
- [README — Docker Compose](README.ru.md#docker-compose)

---

*При изменении пайплайна или модели деплоя обновляйте этот документ и версию в шапке.*
