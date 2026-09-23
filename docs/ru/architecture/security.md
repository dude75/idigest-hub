# Безопасность

## Модель угроз (практическая)

Хаб рассчитан на развёртывание **on-premise / в частной сети**:

- Операторы контролируют `.env`, файлы базы данных и `./data`
- Конечные пользователи не должны получать credentials воркеров
- Backup базы без `.env` не должен раскрывать worker tokens, transcripts или summaries

**Audio blobs:** при `STORAGE_BACKEND=local` файлы на диске **не шифруются** приложением. При `STORAGE_BACKEND=s3` — server-side encryption (SSE) на стороне object storage; hub не делает app-level encrypt/decrypt аудио.

## Секреты в `.env`

| Variable | Назначение |
| -------- | ---------- |
| `HUB_SECRET` | **KEK** (key-encryption key): `SHA-256(secret)` оборачивает DEK в `data_encryption_keys`. Только оператор — не через UI. |
| `HUB_SECRET_PREV` | Прежний `HUB_SECRET` только на время **ротации KEK**. Unwrap: сначала current, затем `PREV`. Удалить из `.env` после переобёртки всех DEK. |
| `SESSION_SECRET` | Pepper для хеширования session tokens и raw значений API token. **Обязателен до `/setup`.** Пустое значение блокирует setup и старт hub, если уже есть sessions или API tokens (fail-closed). |
| `INSTANCE_BOOTSTRAP_TOKEN` | Одноразовый gate для `POST /setup` |
| `OPENAPI_ENABLED` | При `false` отключает `/docs`, `/redoc` и `/openapi.json` (рекомендуется в production). По умолчанию `true` для разработки. |

**Ротация `SESSION_SECRET`** инвалидирует все session cookies и API tokens (хеши перестают совпадать).

## At-rest encryption (envelope)

Чувствительные поля БД — **envelope encryption** (`app/crypto.py`):

1. **KEK** — из `HUB_SECRET` (только `.env` оператора).
2. **DEK** — случайный Fernet-ключ в `data_encryption_keys`; `wrapped_key` = KEK(DEK).
3. **Ciphertext** — формат `v1:{dek_id}:{fernet_token}` в колонках приложения.

Зашифрованные колонки:

- `worker_nodes.api_token_encrypted`
- `transcripts.utterances_encrypted`
- `summaries.body_encrypted`
- `instance_settings.smtp_password_encrypted`
- `instance_settings.download_proxy_password_encrypted`
- `organizations.sso_client_secret_encrypted`
- `users.totp_secret_encrypted`

API расшифровывает на лету — клиенты получают plaintext JSON. Без `.env` дамп БД бесполезен для ciphertext.

При первом старте после апгрейда создаётся первый DEK и мигрируется legacy ciphertext. **Fail-closed при старте:** если инстанс настроен или есть DEK / зашифрованные данные, пустой или неверный `HUB_SECRET` (и при необходимости `HUB_SECRET_PREV`) не даёт поднять процесс (`FATAL` в логах, exit 1).

## Ротация ключей

Две независимые операции:

### Ротация KEK (`HUB_SECRET` — только оператор)

Переоборачивает DEK в БД. **Не** перешифровывает transcripts, summaries, worker tokens.

1. Задать новый `HUB_SECRET` в `.env`.
2. Задать `HUB_SECRET_PREV` = **старый** секрет.
3. Перезапустить hub — переобёртка DEK автоматически при старте (commit после каждого DEK; рестарт посреди процесса безопасен).
4. **Security → Encryption** — убедиться, что `deks_pending_rewrap` = 0 (нет предупреждения).
5. Удалить `HUB_SECRET_PREV` из `.env` и перезапустить.

Держите оба секрета, пока re-wrap не завершён. При падении сервиса — тот же `.env` и рестарт; оставшиеся DEK догонятся.

### Ротация DEK (компрометация data key — UI instance admin)

Перешифровывает все ciphertext на новый DEK. **`HUB_SECRET` менять не нужно.**

1. **Security → Encryption → Добавить DEK** — новый active; прежние active → `retiring`.
2. **Перешифровать и удалить старые DEK** — фоновый job переписывает `v1:{old_dek_id}:…` на active DEK и удаляет неиспользуемые retiring DEK.
3. Следить за job (время запуска/завершения, прогресс по таблицам).

DEK rotation — при компрометации DEK. KEK rotation — при смене мастер-секрета в `.env`.

## Encryption UI

Instance admin: **Security → Encryption** — список DEK, добавление DEK, запуск/отмена re-encrypt job, подсказки про `HUB_SECRET_PREV` / pending KEK re-wrap.

## Session cookies

| Property | Value |
| -------- | ----- |
| Name | `hub_session` |
| Flags | `HttpOnly`, `SameSite=Lax`, `Secure` если `COOKIE_SECURE=true` |
| Storage | Raw token никогда не хранится; в DB — `SHA-256` hash с pepper `SESSION_SECRET` |
| TTL | Настраивается в Instance → Settings (`session_ttl_hours`, по умолчанию 24 ч, макс. 336 ч); sliding при каждом запросе |

Logout удаляет строку session и очищает session и CSRF cookies.

## CSRF-защита

Для cookie-аутентификации **POST**, **PUT**, **PATCH** и **DELETE** под `/api/v1` нужен double-submit token:

| Элемент | Значение |
| ------- | -------- |
| Cookie | `hub_csrf` (доступен SPA, `SameSite=Lax`, `Secure` при `COOKIE_SECURE=true`) |
| Header | `X-CSRF-Token` должен совпадать с cookie |
| Выдача | При login, signup, setup, MFA verify/recover, SSO callback, смене пароля (новая session) |
| Исключения | Публичные auth POST (login, signup, reset, …) и все запросы с **Bearer** API token |

SPA отправляет header автоматически (`web/src/api.ts`).

## API tokens

- Создаются на пользователя: `POST /auth/tokens` (требуется org tariff `api_enabled`)
- Показываются **один раз** в ответе create; для listing хранится только prefix
- Bearer auth включает **rate limits** (per user, IP, global)
- Cookie-сессии не попадают под общие Bearer API-лимиты, но **upload audio** и **создание task** используют те же write-лимиты (`enforce_write_limits`, `rate_limit_api_tasks_*`)
- Отозванные tokens: `DELETE /auth/tokens/{id}`

Пользователи с `must_change_password` или истёкшим org password TTL не могут использовать API tokens.

## Password policy

- Минимум 8 символов на setup, signup, change, reset
- Смена пароля, подтверждение email reset и org admin reset-password отзывают все browser sessions и API tokens пользователя
- Org может задать `password_ttl_days` — после дедлайна разрешены только смена пароля (+ `/me`, logout)
- Org admin может принудительно сбросить (`must_change_password`) через reset-password endpoint

Email сброса пароля требует SMTP **и** **Публичный URL** в Instance settings (`smtp_configured`); иначе `recovery_disabled`.

## Двухфакторная аутентификация (TOTP)

Опциональная **TOTP 2FA** для локальных пользователей (`auth_provider=local`). Включение и отключение — в профиле пользователя.

| Правило | Поведение |
| ------- | --------- |
| Login | Сначала пароль; при включённой 2FA → `mfa_required` + challenge; сессия после TOTP или recovery code |
| Org policy | `organizations.mfa_required` — org admin включает при **выключенном SSO**; принудительный enrollment |
| SSO users | Hub 2FA не применяется; MFA на IdP |
| API token create | Только cookie session; при 2FA → обязателен `totp_code` (step-up) |
| Secret storage | `users.totp_secret_encrypted` (envelope encryption) |
| Recovery | Одноразовые recovery codes при enrollment |

Отключение 2FA блокируется при org policy. Смена пароля / revoke сессий не сбрасывает enrollment.

## Single sign-on (SSO)

OIDC на уровне org (совместим с Keycloak). Authorization Code flow с **PKCE (S256)** и опциональным confidential client secret. Client secrets хранятся зашифрованными (`sso_client_secret_encrypted`). OAuth state (nonce + PKCE verifier) в подписанных payload (TTL 10 мин).

| Правило | Поведение |
| ------- | --------- |
| SSO включён и настроен | password login `org_member` → `sso_login_required` |
| Аварийный вход | `org_admin` и `instance_admin` сохраняют password login |
| Auto-provision | Новый email из IdP → `org_member` в этой org |
| Callback | `{public_base_url}/api/v1/auth/sso/{org_id}/callback` |
| PKCE | `code_challenge` (S256) при authorize; `code_verifier` при token exchange (в подписанном state) |
| `id_token` nonce | Обязателен; должен совпадать с nonce из подписанного OAuth state (fail-closed) |

Требует **Публичный URL** инстанса — как ссылки сброса пароля и URL входа участников SSO.

## OAuth 2.1 provider (MCP)

Опционально (`OAUTH_PROVIDER_ENABLED=true`). Хаб — **authorization server** и MCP **resource server** на `/mcp`. Клиенты (Open WebUI и другие MCP-хосты) проходят Authorization Code + **PKCE S256**, затем вызывают tools с JWT, выданным хабом.

| Правило | Поведение |
| ------- | --------- |
| Кто может authorize | `org_admin` или `org_member` с тарифом `api_enabled` и без блокировок |
| Instance admin без org | Отказ на `/oauth/authorize` (PAT для REST по-прежнему работает) |
| Токены | JWT access + refresh; PAT `idg_…` на `/mcp` **не** принимается |
| Scopes | Гейтят MCP tools (`audio:*`, `transcripts:*`, `summaries:*`, `skills:*`, `tasks:write`). Если не указаны: `transcripts:read` |
| Ключ подписи | `OAUTH_SIGNING_KEY_PEM` или автогенерация `{DATA_DIR}/oauth_signing_key.pem` (JWKS: `/.well-known/jwks.json`) |
| Браузерный UI | HTML login / consent / ошибка; `/oauth/token` и `/oauth/register` остаются JSON |

Каталог tools и карта scope: [MCP API](../api/mcp.md). JWT также работает как `Authorization: Bearer` в REST `/api/v1` (действуют Bearer rate limits).

## Слои авторизации

1. **Authentication** — валидная session, PAT или OAuth JWT хаба
2. **Org membership** — большинство функций требуют `ctx.require_org()`
3. **Role** — `org_admin` vs `org_member` vs `instance_admin`
4. **OAuth scopes** — дополнительный гейт для MCP tools (и отдельных REST-маршрутов) при `via_oauth_token`
5. **Object ownership / share** — см. [roles-and-access](../domain/roles-and-access.md)

Права instance admin отключены во время **impersonation** (`is_instance_admin` false при impersonation).

## Impersonation

Instance admin: `POST /impersonate` с `user_id` устанавливает `sessions.impersonate_user_id`. Эффективный пользователь становится target; actor остаётся admin. Audit log фиксирует действия с actor и on-behalf-of.

Остановка: `DELETE /impersonate`.

## Валидация загрузки аудио

Upload принимает `.wav`, `.mp3`, `.m4a` по расширению **и** проверяет **magic bytes** (RIFF/WAVE, ID3 или MP3 sync word, MP4 `ftyp`) перед сохранением. Несовпадение → `invalid_file`.

## Rate limiting

In-memory token buckets (один процесс). Настраивается в Instance → Settings. Auth endpoints ограничены по email + IP + global; Bearer API — по user + IP + global.

При превышении: HTTP **429**, `error.code = rate_limited`, заголовок `Retry-After`.

См. [deployment](../operations/deployment.md#rate-limiting) и README проекта.

## Client IP за proxy

По умолчанию: `request.client.host` (TCP peer). При пустом `TRUSTED_PROXIES` (дефолт) заголовки `X-Forwarded-For` / `X-Real-IP` игнорируются — безопасно при прямом доступе к hub. Задайте `TRUSTED_PROXIES` (IP/CIDR прокси, напр. `127.0.0.1,::1` с nginx на том же хосте) и настройте заголовки прокси; см. [`deploy/nginx/idigest-hub.conf.example`](../../../deploy/nginx/idigest-hub.conf.example).

Per-IP limits включены по умолчанию (напр. login 60/мин, reset пароля 3/час на email + 10/час на IP). Значение **`0`** в Instance → Settings отключает bucket. Public summary links и PIN unlock — отдельные IP/global buckets.

## Audit log

Таблица `audit_log` — setup, wallet, org create/delete, wipes, impersonation, summary edits, public link policy, `crypto.dek.create`, `crypto.reencrypt.*`. Instance admin: **Security → Audit** — пагинированный API и CSV export; старые строки — в DB.

## Связанные страницы

- [Краткий обзор для аудиторов](../compliance/auditor-brief.md) — каталог контролей, индекс доказательств, mapping фреймворков
- [SECURITY.ru.md](../../../SECURITY.ru.md) — политика CI/CD и чек-лист аудита
- [Роли и доступ](../domain/roles-and-access.md)
- [MCP tools](../api/mcp.md)
- [Деплой](../operations/deployment.md)
