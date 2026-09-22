# Instance API

Требуется auth. Вызывающий должен быть **instance_admin** (не impersonating).

## Workers

### GET `/workers`

Список worker nodes (без `api_token` в ответе). Query: `probe` (по умолчанию `true` — обновить устаревший `/health`), `refresh` (перепробить все включённые ноды).

Каждый item: `last_health`, `dispatch_available` и поля по типу: transcribe — `asr_models[]`, `diarization_models[]`; summarize — `summarize_model` (имя LLM из последнего `/health` или null); capture — `capture_connectors[]`.

В ответе `summary`: счётчики (`total`, `enabled`, `available`, `by_type`), `hub_limits.import_max_concurrent` и `{transcribe,summarize,capture}_capacity` (`max`, `active`, `available`) — агрегат из `health.workers` или fallback по hub-нодам (см. [Воркеры](../operations/workers.md)).

### POST `/workers/probe`

Проверка URL и токена перед сохранением. Тело:

```json
{
  "type": "transcribe",
  "base_url": "http://host.docker.internal:8000",
  "api_token": "worker-secret",
  "worker_id": "uuid"
}
```

`worker_id` опционален при редактировании — если `api_token` не передан, используется сохранённый.

- `transcribe`: `{ "authorized": true, "asr_models": [{ "id", "status" }], "diarization_models": [...] }` — выбирать модели со статусом `loaded` или `unavailable`.
- `capture`: `{ "authorized": true, "connectors": [{ "id", "status", "label" }] }` — выбирать connectors со статусом `loaded`.
- `summarize`: `{ "authorized": true, "health_status": 200, "summarize_model": "..." }`. `summarize_model` есть, если `/health` отдал имя модели.

### POST `/workers`

```json
{
  "type": "transcribe",
  "name": "GPU node 1",
  "base_url": "http://host.docker.internal:8000",
  "api_token": "worker-secret",
  "asr_models": ["whisper", "parakeet"],
  "diarization_models": ["pyannote"],
  "weight": 2,
  "enabled": true
}
```

`type`: `transcribe` | `summarize` | `capture`. Token шифруется at rest.

- Transcribe: `asr_models` обязателен (непустой); модели проверяются по `/health` воркера.
- Capture: `capture_connectors` обязателен (непустой); connectors проверяются по `/health` воркера и whitelist инстанса.

### PATCH `/workers/{id}`

Обновление полей; omit `api_token`, чтобы сохранить существующий. Transcribe: передать `asr_models` / `diarization_models`, чтобы заменить набор моделей ноды. Capture: передать `capture_connectors`, чтобы заменить набор connectors ноды. Опциональный `remediation` (та же форма, что у delete) переписывает prefs и задачи в очереди, если смена убирает модель или connector `jitsi`.

### GET `/workers/{id}/delete-impact`

Превью того, что сломает удаление. `blocking` — true, если от этой ноды ещё что-то зависит.

- Transcribe: `lost_model_pairs`, `available_pairs`, `suggested_replacement`, затронутые пользователи и queued/running задачи, `can_remediate`.
- Summarize: `lost_summarize_models`, `available_summarize_models`, `suggested_summarize_replacement`, затронутые пользователи и задачи, `can_remediate`.
- Capture: `capture_jitsi_hosts`, `capture_tasks_count`, `available_capture_workers`, `suggested_capture_worker`, `can_remediate`.

### POST `/workers/{id}/change-impact`

Тот же impact для предполагаемого обновления (отключить, убрать модели или убрать `jitsi`) без сохранения. Тело — payload PATCH воркера.

### DELETE `/workers/{id}`

Удаление ноды. Опциональное JSON-тело:

```json
{ "remediation": { "summarize_model": "llm-b" } }
```

Передаётся поле, которое соответствует типу ноды:

| Поле | Тип | Эффект |
| ---- | --- | ------ |
| `asr_model`, `diarization_model` | transcribe | Перевести default инстанса, переопределения пользователей и queued/running задачи, которые потеряли бы пару, на пару, которую ещё отдают |
| `summarize_model` | summarize | То же для имени LLM |
| `capture_worker_id` | capture | Перенести карты Jitsi host организаций и queued capture-задачи на другой включённый capture-воркер с `jitsi`. Running capture возвращаются в очередь |

Без `remediation` нода всё равно удаляется. Hub снимает внешние ключи: строки Jitsi host этого воркера удаляются (`cleanup.jitsi_hosts_removed`); у задач, которые на него ссылались, очищается `worker_id` (`cleanup.tasks_updated`). Running capture возвращаются в `queued`. Hub-задачи не помечаются canceled.

Ответ: `{ "status": "ok" }`, плюс `remediation` и/или `cleanup`, если они выполнились. Неизвестная замена → `validation_error`.

## Tariffs

### GET `/tariffs`

Все тарифы с количеством org.

### POST `/tariffs`

Создание tariff (цены как decimal strings).

### PATCH `/tariffs/{id}`

Обновление полей.

### POST `/tariffs/{id}/archive`

### POST `/tariffs/{id}/unarchive`

### DELETE `/tariffs/{id}`

Не выполняется с `tariff_in_use` или `last_tariff`, если заблокировано.

## Organizations

### GET `/orgs`

Список всех org с tariff и списком участников. Query `include_hidden=true` включает org, скрытые из списка instance admin.

### POST `/orgs`

Создание org с начальным org_admin (provisioning в UI instance admin).

```json
{
  "name": "Acme Corp",
  "tariff_id": "uuid",
  "admin_email": "admin@acme.example",
  "admin_password": "minimum-8-chars",
  "locale": "en",
  "is_personal": false
}
```

Возвращает org с `members`. У admin `must_change_password=true`. Ошибки: `email_taken`, `not_found` (неверный tariff).

### POST `/orgs/{org_id}/delete`

Каскадное удаление org. Тело: `{ "confirm_name": "<точное имя org>" }`. Ответ: `{ "status": "ok" }`.

### POST `/orgs/{org_id}/hide`

### POST `/orgs/{org_id}/unhide`

Скрыть/показать org в списке instance admin (per-user `hidden_items`, данные не меняются).

### PATCH `/orgs/{org_id}/tariff`

Назначение любого неархивного tariff.

### POST `/orgs/{org_id}/users/{user_id}/reset-password`

Только instance admin. Сброс пароля активного `org_admin` в этой org. Возвращает `{ "status": "ok", "password": "..." }` (один раз); ставит `must_change_password=true`, отзывает sessions и API tokens. `403 forbidden` для `org_member` и отключённых пользователей.

### POST `/orgs/{org_id}/users/{user_id}/reset-mfa`

Только instance admin. Сбрасывает TOTP 2FA у local-auth пользователя в org с настроенной 2FA. Отзывает sessions и API tokens. Те же ограничения, что у org-admin reset-MFA.

### POST `/orgs/{org_id}/wallet`

```json
{ "delta": "100.00" }
```

Добавляет или вычитает balance. Audit logged.

### GET `/orgs/{org_id}/ledger`

Ledger кошелька org: списания за usage и пополнения instance admin.

Query (те же правила дат, что у stats):

| Param | Описание |
| ----- | -------- |
| `from` | Дата начала `YYYY-MM-DD` |
| `to` | Дата окончания включительно |
| `user_id` | Фильтр списаний по участнику |
| `kind` | `transcribe` или `summarize` |

Возвращает `{ "entries": [...], "total_spent", "total_topup", "net" }`. Типы записей: `charge` (usage) и `wallet` (ручной delta).

## Settings

### GET `/instance/transcribe-models`

Объединение моделей всех включённых transcribe-воркеров плюс defaults инстанса:

```json
{
  "asr_models": ["whisper", "parakeet"],
  "diarization_models": ["pyannote"],
  "default_asr_model": "whisper",
  "default_diarization_model": "pyannote"
}
```

### GET `/instance/summarize-models`

Объединение имён LLM, которые отдают включённые summarize-воркеры, плюс default инстанса:

```json
{
  "summarize_models": ["llm-a", "llm-b"],
  "default_summarize_model": "llm-a"
}
```

Имена берутся из последнего `/health` каждого воркера (`model`, `llm_model` или `llm`).

### GET `/instance/settings`

SMTP host/port/user/from/tls (password не возвращается), `allow_new_orgs`, `public_base_url`, модели транскрибации по умолчанию (`asr_model`, `diarization_model`), списки доступных моделей транскрибации (`asr_models[]`, `diarization_models[]`), модель summarize по умолчанию (`summarize_model`) и `summarize_models[]`, import settings, `date_time_format`, `timezone`, rate limit matrix. Также `smtp_configured`: true только при host, from-address **и** `public_base_url` (нужно для писем сброса пароля и public summary links).

### PATCH `/instance/settings`

Частичное обновление. Поля включают:

- `allow_new_orgs`, `public_base_url`
- SMTP: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `smtp_tls`
- Models: `asr_model`, `diarization_model` (должны быть в объединённом списке воркеров, если воркеры есть; пустой `diarization_model` отключает диаризацию); `summarize_model` (должен быть в `summarize_models`, если воркеры отдают имена)
- Display: `date_time_format` (`eu_24h` | `us_12h` | `iso` | `relative`), `timezone` (`GMT-12` … `GMT+14`)
- Import: `import_enabled`, `import_allowed_extractors`, `download_proxy_*`, `download_cookies_path`, `import_audio_bitrate_kbps`
- Session: `session_ttl_hours`
- Rate limits: `rate_limit_enabled`, `rate_limit_login_email`, `rate_limit_public_link_ip`, `rate_limit_public_pin_ip`, … (см. README)

Изменение rate limits инвалидирует in-memory limit cache.

### POST `/instance/smtp/test-connection`

### POST `/instance/smtp/test-send`

Проверка SMTP. Тело может переопределить host/port/credentials для теста; иначе — сохранённые настройки. `test-send` требует email `to`. Ответ `{ "status": "ok" }` или ошибка SMTP.

## Audit log

### GET `/instance/audit`

Пагинированный audit log. Query: `from`, `to`, `org_id`, `user_id`, `action`, `limit` (по умолчанию 10, max 100), `offset`.

Ответ `{ "items": [...], "total": N }`.

### GET `/instance/audit/export`

Те же фильтры. CSV attachment (`audit-{from}_{to}.csv`).

## Impersonation

### POST `/impersonate`

```json
{ "user_id": "uuid" }
```

Session действует от имени target user. Admin UI показывает impersonation banner.

### DELETE `/impersonate`

Возврат к admin identity.

## Stats

### GET `/instance/stats`

Статистика usage по `usage_events` на уровне инстанса.

Query:

| Param | Описание |
| ----- | -------- |
| `from` | Дата начала `YYYY-MM-DD` (UI по умолчанию — последние 7 дней) |
| `to` | Дата окончания включительно |
| `org_id` | Фильтр по org |
| `user_id` | Фильтр по пользователю |
| `kind` | `transcribe` или `summarize` |

Возвращает счётчики org/user, queued/running tasks, разбивку по дням, итоги (`transcribe_done`, `summarize_done`, `audio_sec`, `summary_chars`, `usage_total`).

## Base skills

Тот же CRUD, что в [skills API](skills.md), под `/skills/base`.

## Encryption (DEK)

Instance admin: UI **Security → Encryption** или API:

### GET `/instance/crypto/deks`

Список DEK с `usage_count`, `active_dek_id`, `deks_pending_rewrap`, `hub_secret_prev_configured`.

### POST `/instance/crypto/deks`

Новый DEK (`active`); прежний active → `retiring`. Audit: `crypto.dek.create`.

### POST `/instance/crypto/reencrypt`

Фоновый job: перешифровка retiring DEK на active, удаление неиспользуемых DEK.

### GET `/instance/crypto/reencrypt/latest`

### GET `/instance/crypto/reencrypt/{job_id}`

### POST `/instance/crypto/reencrypt/{job_id}/cancel`

Ротация KEK (`HUB_SECRET`) — **не API**, только `.env` оператора; переобёртка DEK при рестарте hub. См. [Security — ротация ключей](../architecture/security.md).

## Связанные страницы

- [Billing domain](../domain/billing.md)
- [Workers operations](../operations/workers.md)
- [Security](../architecture/security.md)
