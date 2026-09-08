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

### GET `/instance/orgs`

Список всех org.

### PATCH `/instance/orgs/{org_id}/tariff`

Назначение любого неархивного tariff.

### POST `/instance/orgs/{org_id}/wallet`

```json
{ "delta": "100.00" }
```

Добавляет или вычитает balance. Audit logged.

## Settings

### GET `/instance/settings`

SMTP host/port/user/from/tls (password не возвращается), `allow_new_orgs`, `public_base_url`, ASR models, rate limit matrix.

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

Instance-wide статистика завершённых job.

## Base skills

Тот же CRUD, что в [skills API](skills.md), под `/skills/base`.

## Связанные страницы

- [Billing domain](../domain/billing.md)
- [Workers operations](../operations/workers.md)
- [Security](../architecture/security.md)
