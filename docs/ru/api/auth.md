# Auth API

Префикс: `/api/v1`

## Bootstrap

### GET `/setup/status`

Публичный. `{ "bootstrap_done": true|false }`

### POST `/setup`

Однократное создание instance admin.

```json
{
  "email": "admin@example.com",
  "password": "minimum-8-chars",
  "bootstrap_token": "<INSTANCE_BOOTSTRAP_TOKEN>",
  "locale": "en"
}
```

Успех: устанавливает session cookie, возвращает `{ "status": "ok", "user": {...} }`.

Ошибки: `bootstrap_invalid` (401), `setup_already_done` (409), `email_taken` (409), `rate_limited` (429).

## Регистрация и вход

### GET `/auth/signup-tariffs`

Публичный (после bootstrap). Список тарифов с `available_on_signup` и не в архиве. Пустой, если регистрация отключена.

### POST `/auth/signup`

```json
{
  "email": "user@example.com",
  "password": "minimum-8-chars",
  "tariff_id": "uuid",
  "locale": "ru"
}
```

Создаёт user + org + session. Ошибки: `signup_disabled`, `tariff_not_available`, `email_taken`.

### POST `/auth/login`

```json
{ "email": "...", "password": "..." }
```

Успех: `{ "status": "ok" }` + cookie. Ошибки: `invalid_credentials`, `sso_login_required` (403), когда SSO org включён и пользователь — `org_member`.

### POST `/auth/logout`

Auth опционален. Очищает session.

## SSO (OIDC, совместимый с Keycloak)

На уровне организации. Требует **Публичный URL** инстанса (`public_base_url` в Instance → Settings). Точка входа в браузере: `{public_url}/sso/{org_id}`.

### GET `/auth/sso/{org_id}/info`

Публичный. `{ "org_id", "org_name", "configured", "enabled", "login_url" }`.

### GET `/auth/sso/{org_id}/start`

Публичный. Редирект (302) на authorization URL IdP. Ошибки: `sso_disabled` (403), `sso_misconfigured` (400).

### GET `/auth/sso/{org_id}/callback`

OAuth callback (`code`, `state` в query). При успехе: session cookie, редирект на `{public_base_url}/app`. Ошибки: `sso_disabled`, `sso_misconfigured`, `sso_state_invalid`, `sso_email_missing`, `sso_user_wrong_org`.

Auto-provision: первый SSO-вход с неизвестным email создаёт `org_member` в этой org (email из claims IdP). Существующий пользователь должен принадлежать той же org.

**Пароль при настроенном SSO:** только `org_admin` (аварийный вход). `org_member` после включения SSO использует IdP.

Настройка credentials — [эндпоинты SSO org](org.md#sso).

## Пароль

### POST `/auth/password/change`

Требуется auth. Недоступно при impersonating.

```json
{
  "current_password": "...",
  "new_password": "minimum-8-chars"
}
```

`current_password` опционален, когда `must_change_password` равен true.

Отзывает все остальные browser sessions и API tokens пользователя, затем выдаёт новую session cookie текущему клиенту.

### POST `/auth/password/reset/request`

```json
{ "email": "..." }
```

Всегда возвращает `{ "status": "ok" }` (без перечисления email). Отправляет письмо, если пользователь существует, SMTP настроен и задан **Публичный URL**. Ошибка при отсутствии SMTP или Public URL: `recovery_disabled`. Для пользователей с обязательным SSO (`org_member`) письмо не отправляется.

### POST `/auth/password/reset/confirm`

```json
{
  "token": "from-email-link",
  "new_password": "minimum-8-chars"
}
```

Недействительный или просроченный token → `not_found`.

Отзывает все browser sessions и API tokens пользователя. Новая session не создаётся — после сброса нужен повторный login.

## Текущий пользователь

### GET `/me`

```json
{
  "user": {
    "id", "email", "locale", "default_route",
    "disabled", "must_change_password", "is_instance_admin", "role"
  },
  "org": { ... } | null,
  "impersonating": false,
  "actor": { ... } | null,
  "must_change_password": false
}
```

`role`: `instance_admin` | `org_admin` | `org_member` | null

### PATCH `/me`

```json
{
  "locale": "es",
  "default_route": "tasks"
}
```

`default_route` должен быть разрешён для роли. Ошибка: `validation_error`.

## Резервная копия профиля

### GET `/me/backup`

Требуется auth. Скачивание ZIP или TGZ с данными библиотеки пользователя.

Query (хотя бы один флаг `true`):

| Param | Описание |
| ----- | -------- |
| `transcripts` | Свои transcripts в JSON |
| `summaries` | Свои summaries в JSON |
| `skills` | Свои personal skills в JSON |
| `format` | `zip` (по умолчанию) или `tgz` |

Ответ: `Content-Disposition: attachment` с manifest и выбранными файлами.

## API-токены

Требуют auth + тариф org с `api_enabled` + без блокировки пароля.

### POST `/auth/tokens`

```json
{ "name": "CI pipeline" }
```

Ответ включает одноразовое поле `"token": "idg_..."`.

### GET `/auth/tokens`

Список токенов (только prefix). `blocked_by_tariff`, если API отключён.

### DELETE `/auth/tokens/{token_id}`

Отзыв token.

## Использование с Bearer token

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8080/api/v1/tasks
```

Подчиняется rate limits (Instance → Settings).

## Связанные страницы

- [Security](../architecture/security.md)
- [Roles](../domain/roles-and-access.md)
