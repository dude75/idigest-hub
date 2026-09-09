# Безопасность

## Модель угроз (практическая)

Хаб рассчитан на развёртывание **on-premise / в частной сети**:

- Операторы контролируют `.env`, файлы базы данных и `./data`
- Конечные пользователи не должны получать credentials воркеров
- Backup базы без `.env` не должен раскрывать worker tokens, transcripts или summaries

Аудиофайлы на диске в текущей версии **не шифруются**.

## Секреты в `.env`

| Variable | Назначение |
| -------- | ---------- |
| `HUB_SECRET` | Материал Fernet key: `SHA-256(secret)` → AES-128-CBC + HMAC для at-rest ciphertext в DB |
| `SESSION_SECRET` | Pepper для хеширования session tokens и raw значений API token |
| `INSTANCE_BOOTSTRAP_TOKEN` | Одноразовый gate для `POST /setup` |

**Ротация `HUB_SECRET`** делает существующие зашифрованные строки нечитаемыми (worker tokens, transcript JSON, summary bodies, SMTP password). Автоматического re-encryption нет.

**Ротация `SESSION_SECRET`** инвалидирует все session cookies и API tokens (хеши перестают совпадать).

## At-rest encryption

Зашифрованные колонки (через `app/crypto.py`):

- `worker_nodes.api_token_encrypted`
- `transcripts.utterances_encrypted`
- `summaries.body_encrypted`
- `instance_settings.smtp_password_encrypted`
- `organizations.sso_client_secret_encrypted`

Авторизованные API-ответы расшифровываются на лету — клиенты получают plaintext JSON. Шифрование защищает от утечек только DB.

## Session cookies

| Property | Value |
| -------- | ----- |
| Name | `hub_session` |
| Flags | `HttpOnly`, `SameSite=Lax`, `Secure` если `COOKIE_SECURE=true` |
| Storage | Raw token никогда не хранится; в DB — `SHA-256` hash с pepper `SESSION_SECRET` |
| TTL | 14 days, sliding при каждом запросе |

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

Таблица `audit_log` записывает чувствительные действия (setup, wallet changes, wipes, impersonation, summary edits). В текущей версии не экспонируется через public API — для forensics запрашивайте DB напрямую.

## Связанные страницы

- [Roles and access](../domain/roles-and-access.md)
- [Deployment](../operations/deployment.md)
