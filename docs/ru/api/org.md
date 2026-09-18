# Organization API

Требуется auth. Большинство маршрутов требуют членства в org; admin-маршруты требуют `org_admin`.

## Профиль org

### GET `/org`

Текущая org + tariff + usage total.

### PATCH `/org`

org_admin. `{ "name": "Team Name" }`

### GET `/org/available-tariffs`

Тарифы, доступные для самостоятельного переключения (не в архиве, `available_on_signup`).

### PATCH `/org/tariff`

org_admin. `{ "tariff_id": "uuid" }`

### PATCH `/org/settings`

org_admin.

```json
{
  "password_ttl_days": 90,
  "mfa_required": true,
  "allow_public_links": true
}
```

`password_ttl_days`: `0` отключает TTL.

`mfa_required`: при `true` все local-auth пользователи org должны настроить TOTP 2FA до использования приложения. Взаимоисключимо с SSO — нельзя включить при `sso_enabled`; включение SSO сбрасывает `mfa_required`. SSO-пользователи не подпадают под Hub 2FA.

`allow_public_links`: при `false` участники не могут создавать public links, гостевые URL возвращают `not_found`.

## Публичные ссылки на summary

Участники org управляют ссылками на странице **Public links** в навигации (или в диалоге шаринга summary).

### GET `/org/public-links`

Список активных и отозванных ссылок org. **org_member** видит только свои summary; **org_admin** — все.

Каждый item: `id`, `summary_id`, `summary_title`, `url`, `expires_at`, `pin_required`, `owner_email`, `active`, `created_at`, `revoked`.

### DELETE `/org/public-links/{link_id}`

Отзыв по id ссылки. Владелец — свои; org_admin — любые в org.

## SSO

org_admin. OIDC, совместимый с Keycloak, на уровне организации. Требует **Публичный URL** инстанса.

### GET `/org/sso`

Admin-представление: `issuer`, `client_id`, `has_client_secret`, `enabled`, `configured`, `public_base_url_set`, `login_url`, `callback_url` (redirect URI для Keycloak **Valid redirect URIs**).

### PATCH `/org/sso`

```json
{
  "issuer": "https://keycloak.example.com/realms/myrealm",
  "client_id": "idigest-hub",
  "client_secret": "optional-on-update",
  "clear_client_secret": false,
  "enabled": true
}
```

Omit `client_secret`, чтобы сохранить текущий секрет. `clear_client_secret: true` — удалить секрет.

Ошибки: `sso_misconfigured` при включении без issuer/client/секрета или Public URL.

URL входа участников: `{public_url}/sso/{org_id}` (также в ответе GET при заданном Public URL).

## Статистика

### GET `/org/stats`

org_admin. Query:

| Param | Описание |
| ----- | -------- |
| `from` | Дата начала `YYYY-MM-DD` |
| `to` | Дата окончания включительно |
| `user_id` | Фильтр по участнику |
| `kind` | `transcribe` или `summarize` |

Возвращает ежедневную разбивку и итоги из `usage_events`.

## Пользователи

### GET `/org/users`

Список участников с ролями.

### POST `/org/users`

org_admin. Создание участника:

```json
{
  "email": "new@example.com",
  "password": "minimum-8",
  "role": "org_member",
  "locale": "en"
}
```

### PATCH `/org/users/{user_id}`

Смена роли (`org_admin` | `org_member`).

### POST `/org/users/{user_id}/disable`

### POST `/org/users/{user_id}/enable`

### POST `/org/users/{user_id}/reset-password`

Генерирует случайный пароль, `must_change_password=true`, отзывает sessions/tokens.

Возвращает `{ "status": "ok", "password": "..." }` — показать админу один раз (модалка в UI).

### POST `/org/users/{user_id}/reset-mfa`

org_admin. Сбрасывает TOTP и recovery codes у local-auth участника с настроенной 2FA. Отзывает sessions и API tokens. Ошибка, если 2FA не настроена. SSO-пользователи: `forbidden`.

### POST `/org/users/{user_id}/offboard`

```json
{
  "action": "transfer|wipe",
  "target_user_id": "uuid"
}
```

`target_user_id` обязателен для `transfer`.

## Связанные страницы

- [Organizations domain](../domain/organizations.md)
- [Roles](../domain/roles-and-access.md)
