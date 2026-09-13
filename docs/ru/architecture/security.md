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
| `SESSION_SECRET` | Pepper для хеширования session tokens и raw значений API token |
| `INSTANCE_BOOTSTRAP_TOKEN` | Одноразовый gate для `POST /setup` |

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

Logout удаляет строку session и очищает cookie.

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

## Single sign-on (SSO)

OIDC на уровне org (совместим с Keycloak). Client secrets хранятся зашифрованными (`sso_client_secret_encrypted`). OAuth state/nonce в подписанных cookies (TTL 10 мин).

| Правило | Поведение |
| ------- | --------- |
| SSO включён и настроен | password login `org_member` → `sso_login_required` |
| Аварийный вход | `org_admin` и `instance_admin` сохраняют password login |
| Auto-provision | Новый email из IdP → `org_member` в этой org |
| Callback | `{public_base_url}/api/v1/auth/sso/{org_id}/callback` |
| `id_token` nonce | Обязателен; должен совпадать с nonce из подписанного OAuth state (fail-closed) |

Требует **Публичный URL** инстанса — как ссылки сброса пароля и URL входа участников SSO.

## Слои авторизации

1. **Authentication** — валидная session или Bearer token
2. **Org membership** — большинство функций требуют `ctx.require_org()`
3. **Role** — `org_admin` vs `org_member` vs `instance_admin`
4. **Object ownership / share** — см. [roles-and-access](../domain/roles-and-access.md)

Права instance admin отключены во время **impersonation** (`is_instance_admin` false при impersonation).

## Impersonation

Instance admin: `POST /impersonate` с `user_id` устанавливает `sessions.impersonate_user_id`. Эффективный пользователь становится target; actor остаётся admin. Audit log фиксирует действия с actor и on-behalf-of.

Остановка: `DELETE /impersonate`.

## Rate limiting

In-memory token buckets (один процесс). Настраивается в Instance → Settings. Auth endpoints ограничены по email + IP + global; Bearer API — по user + IP + global.

При превышении: HTTP **429**, `error.code = rate_limited`, заголовок `Retry-After`.

См. [deployment](../operations/deployment.md#rate-limiting) и README проекта.

## Client IP за proxy

По умолчанию: `request.client.host` (TCP peer). При пустом `TRUSTED_PROXIES` (дефолт) заголовки `X-Forwarded-For` / `X-Real-IP` игнорируются — безопасно при прямом доступе к hub. Задайте `TRUSTED_PROXIES` (IP/CIDR прокси, напр. `127.0.0.1,::1` с nginx на том же хосте) и настройте заголовки прокси; см. [`deploy/nginx/idigest-hub.conf.example`](../../../deploy/nginx/idigest-hub.conf.example). Per-IP limits по умолчанию **0 (off)**, пока не настроены в Instance → Settings.

## Audit log

Таблица `audit_log` — setup, wallet, wipes, impersonation, summary edits, `crypto.dek.create`, `crypto.reencrypt.*`. Instance admin: **Security → Audit** через API; старые строки — в DB.

## Связанные страницы

- [Roles and access](../domain/roles-and-access.md)
- [Deployment](../operations/deployment.md)
