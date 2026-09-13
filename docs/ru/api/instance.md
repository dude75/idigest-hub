# Instance API

Требуется auth. Вызывающий должен быть **instance_admin** (не impersonating).

## Workers

### GET `/workers`

Список worker nodes (без api_token в ответе).

### POST `/workers`

```json
{
  "type": "transcribe",
  "name": "GPU node 1",
  "base_url": "http://host.docker.internal:8000",
  "api_token": "worker-secret",
  "weight": 2,
  "enabled": true
}
```

`type`: `transcribe` | `summarize`. Token шифруется at rest.

### PATCH `/workers/{id}`

Обновление полей; omit `api_token`, чтобы сохранить существующий.

### DELETE `/workers/{id}`

Удаление node (не отменяет автоматически hub tasks in-flight).

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

Список всех org с tariff и списком участников.

### PATCH `/orgs/{org_id}/tariff`

Назначение любого неархивного tariff.

### POST `/orgs/{org_id}/users/{user_id}/reset-password`

Только instance admin. Сброс пароля активного `org_admin` в этой org. Возвращает временный пароль; ставит `must_change_password=true`, отзывает sessions и API tokens. `403 forbidden` для `org_member` и отключённых пользователей.

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

### GET `/instance/settings`

SMTP host/port/user/from/tls (password не возвращается), `allow_new_orgs`, `public_base_url`, ASR models, rate limit matrix. Также `smtp_configured`: true только при host, from-address **и** `public_base_url` (нужно для писем сброса пароля).

### PATCH `/instance/settings`

Частичное обновление. Поля включают:

- `allow_new_orgs`, `public_base_url`
- SMTP: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `smtp_tls`
- Models: `asr_model`, `diarization_model`
- Rate limits: `rate_limit_enabled`, `rate_limit_login_email`, … (см. README)

Изменение rate limits инвалидирует in-memory limit cache.

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
