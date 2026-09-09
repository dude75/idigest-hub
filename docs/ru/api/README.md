# Обзор API

Базовый путь: **`/api/v1`**

Интерактивная схема OpenAPI: `{origin}/openapi.json` (автоматически генерируется FastAPI). Swagger UI: `{origin}/docs` — **Authorize** для session cookie (`hub_session`) или Bearer API token (`idg_…` из `POST /auth/tokens`).

## Формат ответа

### Успех

Большинство эндпоинтов возвращают JSON-объекты напрямую, например `{ "status": "ok" }` или полезную нагрузку сущности.

Создание задачи возвращает **202** с телом задачи (без обёртки).

### Ошибка

```json
{
  "status": "error",
  "error": {
    "code": "not_found",
    "message": "Human-readable localized message"
  }
}
```

`message` следует заголовку `Accept-Language` / локали пользователя (`en`, `ru`, `es`).

## Аутентификация

| Метод | Заголовок / cookie | Ограничение частоты |
| ----- | ------------------ | ------------------- |
| Сессия | Cookie `hub_session` | Auth; upload + создание task — те же write limits, что у Bearer |
| API-токен | `Authorization: Bearer <token>` | Да (Bearer + write limits на upload/tasks) |

Неаутентифицированные запросы к защищённым маршрутам → **401** `unauthorized`.

## Общие HTTP-коды состояния

| Код | Когда |
| --- | ----- |
| 200 | OK |
| 202 | Задача принята |
| 400 | `validation_error`, некорректный ввод |
| 401 | Ошибки auth, `bootstrap_invalid` |
| 403 | `forbidden`, `signup_disabled`, `api_disabled`, `must_change_password` |
| 404 | `not_found` |
| 409 | `conflict`, `email_taken`, `setup_already_done`, `task_running`, … |
| 413 | `payload_too_large`, `text_too_long` |
| 429 | `rate_limited`, `insufficient_balance` |

## Коды ошибок

| code | HTTP | Значение |
| ---- | ---- | -------- |
| `unauthorized` | 401 | Отсутствует или недействителен session или token |
| `invalid_credentials` | 401 | Неверный email/пароль |
| `bootstrap_invalid` | 401 | Неверный bootstrap token при setup |
| `forbidden` | 403 | Недостаточная роль |
| `must_change_password` | 403 | Требуется смена пароля |
| `signup_disabled` | 403 | Регистрация закрыта |
| `recovery_disabled` | 403 | SMTP или Public URL не настроены |
| `sso_login_required` | 403 | Пароль запрещён; используйте SSO org |
| `sso_disabled` | 403 | SSO не включён для org |
| `sso_misconfigured` | 400 | Нет issuer/client/secret или Public URL |
| `sso_state_invalid` | 400 | Неверный или просроченный OAuth state |
| `sso_email_missing` | 400 | В токене IdP нет email |
| `sso_user_wrong_org` | 403 | Пользователь принадлежит другой org |
| `api_disabled` | 403 | Тариф отключает API |
| `not_found` | 404 | Ресурс или маршрут |
| `validation_error` | 400 | Некорректное body/query |
| `invalid_file` | 400 | Некорректная загрузка |
| `payload_too_large` | 413 | Слишком большая загрузка |
| `text_too_long` | 413 | Слишком большой ввод для summarize |
| `insufficient_balance` | 429 | Пустой кошелёк |
| `rate_limited` | 429 | Слишком много запросов (+ `Retry-After`) |
| `setup_already_done` | 409 | Bootstrap уже выполнен |
| `email_taken` | 409 | Дубликат email |
| `tariff_not_available` | 400 | Недопустимый выбор тарифа |
| `last_org_admin` | 409 | Будет удалён последний admin |
| `tariff_in_use` | 409 | Нельзя удалить тариф |
| `last_tariff` | 409 | Нельзя удалить последний тариф |
| `task_running` | 409 | Отмена отклонена |
| `conflict` | 409 | Общий конфликт |

Ошибки на уровне задачи (worker pipeline) появляются в объекте задачи как `error.code`, не всегда входят в этот enum.

## Health

```
GET /api/v1/health
```

Без auth. Возвращает `{ "status": "ok", "version": "..." }`.

## Индекс эндпоинтов

| Область | Документ |
| ------- | -------- |
| Setup, auth, me, tokens | [auth.md](auth.md) |
| Задачи | [tasks.md](tasks.md) |
| Аудио, транскрипты, саммари, shares | [library.md](library.md) |
| Администрирование организации | [org.md](org.md) |
| Администрирование инстанса | [instance.md](instance.md) |
| Каталог skills | [skills.md](skills.md) |

## Соглашения

- UUID везде как строки
- Деньги как десятичные строки в JSON (`"12.34"`)
- Временные метки ISO 8601 с часовым поясом
- Email при записи нормализуется в нижний регистр

## Связанные страницы

- [Security](../architecture/security.md)
- [Development setup](../development/setup.md)
