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

Успех: `{ "status": "ok" }` + cookie. Ошибка: `invalid_credentials`.

### POST `/auth/logout`

Auth опционален. Очищает session.

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

### POST `/auth/password/reset/request`

```json
{ "email": "..." }
```

Всегда возвращает `{ "status": "ok" }` (без перечисления email). Отправляет письмо, если пользователь существует и SMTP настроен. Ошибка при отсутствии SMTP: `recovery_disabled`.

### POST `/auth/password/reset/confirm`

```json
{
  "token": "from-email-link",
  "new_password": "minimum-8-chars"
}
```

Недействительный или просроченный token → `not_found`.

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

## API-токены

Требуют auth + тариф org с `api_enabled` + без блокировки пароля.

### POST `/auth/tokens`

```json
{ "name": "CI pipeline" }
```

Ответ включает одноразовое поле `"token": "hub_..."`.

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
