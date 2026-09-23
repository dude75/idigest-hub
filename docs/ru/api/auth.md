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

Успех (без 2FA): `{ "status": "ok" }` + session cookie.

Если у пользователя включён TOTP 2FA (только local auth): `{ "status": "mfa_required", "challenge_id": "..." }` — cookie пока не выдаётся. Завершите вход через [MFA verify](#post-authmfaverify) или [MFA recover](#post-authmfarecover). TTL challenge: 5 минут.

Ошибки: `invalid_credentials`, `sso_login_required` (403), когда SSO org включён и пользователь — `org_member`.

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

## OAuth 2.1 provider (MCP / Open WebUI)

Опционально (`OAUTH_PROVIDER_ENABLED=true` в `.env`). Хаб выступает **Authorization Server** и встроенный **MCP** (`/mcp`, Streamable HTTP). Требуется **Публичный URL**; canonical resource URI = `{public_url}/mcp` (override: `OAUTH_MCP_RESOURCE_URL`).

Discovery: `GET /.well-known/oauth-authorization-server`, `GET /.well-known/jwks.json`.

Регистрация клиента (DCR): `POST /oauth/register`. Authorization Code + **PKCE S256**: `GET /oauth/authorize`, `POST /oauth/token`.

Access token (JWT) принимается в API как `Authorization: Bearer` наряду с PAT (`idg_…`). Scope v1: `transcripts:read` — `GET /transcripts`, `GET /transcripts/{id}`. Пользователь без org membership (instance admin без org) OAuth-токен для library не получит на authorize.

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

## Двухфакторная аутентификация (TOTP)

Только local-пользователи (`auth_provider=local`). SSO-пользователи используют MFA IdP — Hub 2FA для них не применяется.

### POST `/auth/mfa/verify`

Публичный (без session). Завершение входа после `mfa_required`:

```json
{ "challenge_id": "...", "code": "123456" }
```

Успех: `{ "status": "ok" }` + session cookie. Ошибки: `mfa_challenge_invalid` (401), `invalid_totp` (401), `rate_limited` (429).

### POST `/auth/mfa/recover`

Публичный. Тот же сценарий с одноразовым recovery code вместо TOTP:

```json
{ "challenge_id": "...", "recovery_code": "..." }
```

Успех: `{ "status": "ok" }` + session cookie. Recovery code сгорает. Те же ошибки, что у verify.

### GET `/auth/mfa/status`

Требуется auth. `{ "enabled": bool, "required": bool, "enrollment_required": bool }`.

- `required` — политика org `mfa_required` применяется к пользователю (SSO выключен, local auth).
- `enrollment_required` — политика требует 2FA, но пользователь ещё не настроил; большинство эндпоинтов вернёт `mfa_enrollment_required` (403) до подтверждения setup.

### POST `/auth/mfa/setup/start`

Требуется auth. Недоступно при impersonating и для SSO-пользователей.

Возвращает `{ "secret": "...", "otpauth_uri": "otpauth://..." }` для приложения-аутентификатора. Секрет сохраняется до подтверждения.

### POST `/auth/mfa/setup/confirm`

Требуется auth.

```json
{ "code": "123456" }
```

Проверяет pending-секрет и включает 2FA. Ответ: `{ "status": "ok", "recovery_codes": ["...", ...] }` (8 одноразовых кодов). Ошибка: `invalid_totp`.

### POST `/auth/mfa/disable`

Требуется auth. Отключение инициирует пользователь.

```json
{ "password": "...", "code": "123456" }
```

`code` — TOTP или recovery code. Заблокировано, если org требует 2FA (`forbidden`). При успехе отзывает все sessions и API tokens. Ошибки: `invalid_credentials`, `invalid_totp`.

Сброс админом (без кода пользователя): [Org reset-MFA](org.md#post-orgusersuser_idreset-mfa), [Instance reset-MFA](instance.md#post-orgsorg_idusersuser_idreset-mfa).

## Текущий пользователь

### GET `/me`

```json
{
  "user": {
    "id", "email", "locale", "default_route",
    "date_time_format", "timezone",
    "asr_model", "diarization_model", "summarize_model",
    "disabled", "must_change_password", "is_instance_admin", "role"
  },
  "org": { ... } | null,
  "impersonating": false,
  "actor": { ... } | null,
  "date_time_prefs": { ... },
  "transcribe_prefs": {
    "asr_model", "diarization_model",
    "asr_source", "diarization_source",
    "instance_asr_model", "instance_diarization_model"
  },
  "transcribe_models": { "asr_models": [], "diarization_models": [] },
  "summarize_prefs": {
    "summarize_model", "source", "instance_summarize_model"
  },
  "summarize_models": { "summarize_models": [] },
  "must_change_password": false,
  "mfa_enabled": false,
  "mfa_required": false,
  "mfa_enrollment_required": false
}
```

`role`: `instance_admin` | `org_admin` | `org_member` | null

При `mfa_enrollment_required: true` до настройки 2FA доступны только смена пароля, MFA setup, `/me` и logout.

### PATCH `/me`

```json
{
  "locale": "es",
  "default_route": "tasks",
  "date_time_format": "us_12h",
  "timezone": "GMT+3",
  "asr_model": "parakeet",
  "diarization_model": "",
  "summarize_model": "llm-b"
}
```

`default_route` должен быть разрешён для роли. Ошибка: `validation_error`.

`date_time_format`: `eu_24h` | `us_12h` | `iso` | `relative`, или `null` — наследовать default инстанса.

`timezone`: `GMT-12` … `GMT+14`, или `null` — наследовать default инстанса. Разрешённые значения возвращаются в GET `/me`.

`asr_model`: id модели из `transcribe_models.asr_models`, или `null` — наследовать default инстанса.

`diarization_model`: id из `transcribe_models.diarization_models`, `null` — наследовать default инстанса, или `""` — отключить диаризацию для своих задач.

`summarize_model`: имя из `summarize_models.summarize_models`, или `null` — наследовать default инстанса. Разрешённое значение в `summarize_prefs` (`source`: `user` или `instance`). Неизвестное имя → `validation_error`.

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

Только cookie session (не через Bearer). Заблокировано во время MFA enrollment (`mfa_enrollment_required`).

```json
{ "name": "CI pipeline", "totp_code": "123456" }
```

`totp_code` обязателен, если у пользователя включена 2FA (`mfa_step_up_required`, если пропущен). Ответ включает одноразовое поле `"token": "idg_..."`.

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
