# Организации

**Организация (organization)** — граница изоляции биллинга и данных. Каждый обычный пользователь принадлежит ровно одной org через `memberships`.

## Пути создания

### Signup (`POST /auth/signup`)

1. Инстанс должен быть инициализирован (`bootstrap_done`)
2. `allow_new_orgs` должен быть `true`
3. Должен существовать хотя бы один неархивированный тариф с `available_on_signup=true`
4. Создаются пользователь + персональная org (`is_personal=true`, имя из local-part email)
5. Пользователь становится `org_admin`
6. Начальный баланс = `signup_credit` (или `0`, если тариф `unlimited`)

### Приглашения org admin (`POST /org/users`)

org admin создаёт пользователей с email, паролем, ролью (`org_admin` | `org_member`), locale. Новый пользователь добавляется в **ту же org**.

## Профиль org

| Поле | Кто редактирует | Примечания |
| ---- | --------------- | ---------- |
| `name` | org_admin | Отображаемое имя |
| `tariff_id` | org_admin (сам) или instance_admin | Должен быть неархивированным и с `available_on_signup` для самообслуживания |
| `password_ttl_days` | org_admin | `0` = отключено; принудительная периодическая смена пароля |
| `balance` | instance_admin (кошелёк) | Decimal(12,2), при списании округляется вниз до центов |

GET `/org` возвращает org + вложенный tariff + итог использования (`sum(usage_events.amount)`).

## Смена тарифа

**org admin** — `PATCH /org/tariff`: только тарифы, которые активны и помечены `available_on_signup`.

**instance admin** — `PATCH /orgs/{org_id}/tariff`: может назначить любой неархивированный тариф.

Смена тарифа **не** меняет зафиксированные на задачах цены.

## Жизненный цикл пользователя

| Действие | Endpoint | Примечания |
| -------- | -------- | ---------- |
| Смена роли | `PATCH /org/users/{id}` | Нельзя понизить последнего org admin |
| Отключение | `POST /org/users/{id}/disable` | Инвалидирует сессии + API-токены |
| Включение | `POST /org/users/{id}/enable` | |
| Сброс пароля админом | `POST /org/users/{id}/reset-password` | Случайный пароль, `must_change_password=true` |
| Offboarding | `POST /org/users/{id}/offboard` | См. ниже |

## Offboarding

Тело `POST /org/users/{id}/offboard`:

| action | Поведение |
| ------ | --------- |
| `transfer` | Переназначить артефакты на `target_user_id` (та же org) |
| `wipe` | Жёстко удалить контент пользователя |

Ограничение: нельзя offboard последнего org admin без замены.

## Статистика

`GET /org/stats?from=YYYY-MM-DD&to=YYYY-MM-DD` — только org_admin.

Агрегирует `usage_events` по дню, пользователю, kind (`transcribe` | `summarize`). Опциональные фильтры: `user_id`, `kind`.

Статистика уровня инстанса: `GET /instance/stats` с фильтрами даты/org/user/kind (instance admin). Ledger кошелька: `GET /orgs/{org_id}/ledger`.

## Single sign-on (SSO)

У каждой org может быть **OIDC SSO** (совместим с Keycloak):

1. instance admin задаёт **Публичный URL** в Instance → Settings.
2. org admin настраивает issuer, client ID и secret в Org → SSO; копирует **callback URL** в Keycloak.
3. При `sso_enabled` участники `org_member` входят по `{public_url}/sso/{org_id}`; пароль для них заблокирован (`sso_login_required`).
4. `org_admin` сохраняет пароль как аварийный вход.

GET `/org` включает `sso: { configured, enabled, login_url }`. Auto-provision создаёт новых участников при первом SSO-входе (email из IdP).

## Отключение signup

instance admin выставляет `allow_new_orgs=false` или архивирует все signup-тарифы → новые signup возвращают `signup_disabled` (HTTP 403).

Существующие org продолжают работать.

## Персональные vs командные org

`is_personal=true` для org, созданных при signup. Поведенческой разницы в API нет — флаг информационный для UI.

## Связанные страницы

- [Биллинг](billing.md)
- [Роли и доступ](roles-and-access.md)
- [Org API](../api/org.md)
