# Public API (без аутентификации)

Префикс: `/api/v1`

Без session и API token. **Read-only гостевой доступ** к summary по публичным ссылкам.

Требуется **Публичный URL** (`public_base_url`). У org должно быть `allow_public_links=true` (по умолчанию). Владелец создаёт ссылки в UI библиотеки или через auth API — см. [Library API — public links](library.md#публичные-ссылки-на-summary).

## GET `/public/summary/{token}`

Возвращает body summary для активной ссылки.

**Без PIN:** `{ "pin_required": false, "title", "body", "created_at", ... }`

**С PIN (ещё не разблокировано):** `{ "pin_required": true }` — без body.

**Ошибки:** `not_found` (404) — неверный, просроченный, отозванный token или политика org отключила ссылки.

Rate limit по IP клиента и global (Instance → Settings). CSRF не требуется.

## POST `/public/summary/{token}/unlock`

Отправка PIN, если ссылка его требует.

```json
{ "pin": "1234" }
```

PIN: 4–6 цифр. При успехе: `{ "pin_required": false, ... }` и payload summary; HttpOnly cookie разблокировки (`hub_plu`, 30 мин) — повторные GET без PIN.

**Ошибки:** `not_found` (404), `invalid_pin` (401).

Отдельный bucket rate limit для попыток PIN (`rate_limit_public_pin_ip`).

## Связанные страницы

- [Домен Library — public links](../domain/library.md#публичные-ссылки-на-summary)
- [Organization API — политика public links](org.md#публичные-ссылки-на-summary)
- [Instance API — rate limits](instance.md#settings)
