# Структура frontend

React 19 + TypeScript + Vite. Source: `web/src/`. README пакета: [web/README.md](../../../web/README.md).

## UI stack

| Слой | Где / пакет |
| ---- | ----------- |
| shadcn (стиль `base-nova`) | `web/components.json`, CLI `shadcn` |
| Примитивы | `web/src/components/ui/` (Base UI + Tailwind) |
| App-обёртки | `web/src/components/app/` — формы, admin-таблицы, общие контролы |
| Иконки | `lucide-react` (`iconLibrary: lucide` в `components.json`) |
| Шрифт | Geist через `@fontsource-variable/geist` в `index.css` |
| Стили | Tailwind CSS v4 (`@tailwindcss/vite`) |
| Уведомления | `sonner` (`showError` / toast в `util.tsx`) |

Новые экраны собирайте из **shadcn-примитивов** и **App\***, без legacy global CSS (`.btn`, `.card`, произвольный `.stack`). Primary save/create — общий паттерн submit-кнопки; CI проверяет через `npm run check:ui` (`web/scripts/check-ui-migration.mjs`, правила в `web/scripts/ui-migration-rules.mjs`; в GitLab CI вместе с `npm test` и `npm run build`). Guard также падает, если в `web/src/index.css` снова появляются запрещённые legacy-правила (глобали SPA — Tailwind-токены и shadcn; OAuth HTML — отдельный `auth-shell.css`). Те же правила в Vitest: `web/src/ui/legacyUiGuard.test.ts`.

### Типографика и layout-токены

| Модуль | Назначение |
| ------ | ---------- |
| `components/app/appTypography.ts` | Общие Tailwind-классы (`appListRowTitle`, `appFormStack`, `ingestStudioCardChrome`, …) |
| `typography.ts` | Reading surfaces (`hub-reading-surface`, `summary-body`) и re-export для страниц и `typography.test.ts` |
| `components/ListRow.tsx` | Строки списков library/admin (`listRowLayout`, meta через `appListRowMeta`) |
| `components/EntityPageTitle.tsx` | Заголовки карточек объектов |
| `components/app/HubBadge.tsx` | Статус-чипы (вместо legacy `.badge`) |

Импортируйте токены из `appTypography` / `typography`, а не новые разовые `text-muted-foreground` и не удалённые global-классы.

### Code splitting

`App.tsx` подгружает тяжёлые маршруты через `React.lazy` + `Suspense` (fallback `common.loading`): **Instance**, **Library**, **Org**, **Stats**, **Security**. Auth, setup, ingest detail, tasks, skills и profile остаются в основном chunk.

`vite.config.ts` выносит **recharts** и **markdown**-зависимости в именованные vendor chunks.

## Дерево исходников (обзор)

```
web/src/
├── main.tsx          # Entry
├── App.tsx           # Router shell, auth gates
├── auth.tsx          # Session context, login state
├── api.ts            # fetch wrappers for /api/v1
├── routes.ts         # Path helpers, default_route logic
├── types.ts          # Доменные типы; многие — алиасы OpenAPI через openapi/contracts.ts
├── openapi/          # Сгенерированная схема + алиасы (см. ниже)
├── i18n.ts           # i18next setup
├── locales/          # en.json, ru.json, es.json
├── pages/
│   ├── LandingPage, LoginPage, SignupPage, SetupPage, SsoLoginPage
│   ├── Verify2faPage, Enroll2faPage, ChangePasswordPage, ForgotPage, ResetPage
│   ├── AcceptAgreementPage, LegalDocumentPage
│   ├── LibraryPage, AudioPage, TranscriptPage, SummaryPage, PublicLinksPage
│   ├── TasksPage, TaskPage, SkillsPage, SkillPage
│   ├── OrgPage, StatsPage, ProfilePage (+ `pages/profile/*` вкладки), PublicSummaryPage (guest)
│   ├── instance/     # InstancePage + вкладки (workers, tariffs, orgs, …)
│   └── security/     # SecurityPage (encryption, audit log)
├── mfa.ts            # sessionStorage helpers для login challenge_id
├── context/
│   └── meTelegram.tsx        # Общий статус /me/telegram и опрос при привязке
├── shell/
│   ├── constants.ts          # PROFILE_TELEGRAM_SECTION_ID (якорь в профиле)
│   └── telegramPrompt.ts     # Когда показывать иконку Telegram в shell
└── components/
    ├── ui/           # shadcn primitives
    ├── app/          # AppField, AppFormActions, AdminDataTable, …
    ├── auth/         # Auth card/field chrome
    ├── Shell.tsx     # Nav layout; оборачивает MeTelegramProvider
    ├── GlobalMicRecordAccess.tsx # Плавающие микрофон и подсказка Telegram (участники org)
    ├── TelegramIcon.tsx
    ├── AdminSection.tsx
    ├── MicrophoneRecordModal.tsx   # Запись с микрофона → POST /audios
    ├── IngestPipelinePanel.tsx     # Карточка ingest: transcribe + один skill для summarize
    ├── SummarizeSkillRadioGroup.tsx  # Выбор одного skill (pipeline Library, summarize на Transcript)
    ├── IngestExtraTagsMultiSelect.tsx  # Library URL ingest: модалка доп. тегов → user_tags на import/capture
    ├── ShareDialog.tsx, MfaSetupPanel.tsx, …
    └── …
```

Вкладки `InstancePage` и маршруты выше — lazy; см. [Code splitting](#code-splitting).

## Routing

Public: `/`, `/login`, `/signup`, `/setup`, `/forgot`, `/reset`, `/verify-2fa`, `/enroll-2fa`, `/change-password`, `/accept-agreement`, `/sso/:orgId`, `/public/summary/:token`, `/legal/:slug`.

Приложение: `/app/*` (library с `:tab`, детали audio/transcript/summary, skills, org, stats, profile, tasks, instance, security, public-links).

`resolveHomePath(me)` в `routes.ts` выбирает landing page из user `default_route` и role.

## API client

`api.ts` использует `fetch` с `credentials: 'include'` для cookie auth. Same origin в production; Vite proxy в dev (см. [setup](setup.md) про `HUB_PORT`).

Errors ожидают `{ status: "error", error: { code, message } }`. Ошибки API показываются toast-уведомлениями справа сверху (`sonner` через `util.tsx` `showError`).

## API types (OpenAPI)

TypeScript UI синхронизируется с контрактом backend:

| Артефакт | Назначение |
| -------- | ---------- |
| `web/openapi/openapi.json` | Закоммиченный snapshot OpenAPI (скрипт экспорта, без живого сервера) |
| `web/src/openapi/schema.gen.ts` | Сгенерированные `components` / `paths` (`openapi-typescript`) |
| `web/src/openapi/contracts.ts` | Алиасы `Schema*` и list-envelope; в pages — `import` из `../openapi` |
| `web/src/types.ts` | Имена для приложения (`Me`, `Task`, `Org`, …); где совпадает — re-export OpenAPI |

После изменения backend `response_model` или routes:

```bash
cd web
npm run generate:api    # export_openapi.py + generate:api-types
```

В новом и затронутом коде предпочитайте `api<SchemaFooResponse>(…)` вместо inline `api<{ … }>(…)`. Списки с доп. UI-полями (например `ShareBadge`) — через helpers в `contracts.ts`. `Me` — небольшой гибрид над `SchemaMeResponse` (prefs и legal).

Перегенерация косвенно проверяется в CI: pytest `tests/test_export_openapi.py` и `npm run build`.

## Auth flow

1. `GET /me` при загрузке
2. Redirect на `/login` при 401
3. `resolveAuthBlockPath(me)` в `routes.ts`:
   - `must_change_password` → `/change-password`
   - `mfa_enrollment_required` → `/enroll-2fa` (политика org; setup через `MfaSetupPanel`)
4. Login с 2FA: `POST /auth/login` возвращает `mfa_required` → `challenge_id` в `sessionStorage` (`mfa.ts`) → `/verify-2fa` → `POST /auth/mfa/verify` или `/recover`
5. После login / смены пароля / verify или enroll 2FA → `resolveAuthContinuationPath(me)` → home
6. Instance admin без org → Instance UI

Настройки профиля используют те же API (`PATCH /me`, `/auth/tokens`, `/me/backup`, …); изменилась только вёрстка. Org admin: `mfa_required` и reset-MFA участников — на странице **Org**. Модалки Instance → Workers / Tariffs без изменений (`WorkerImpactModal`, `TariffImpactModal`).

## Страница профиля (`/app/profile`)

Точка входа: `web/src/pages/ProfilePage.tsx`; вкладки и формы — `web/src/pages/profile/` (`useProfilePageModel`, `ProfilePageProvider`).

**Вкладки** (shadcn `Tabs`, обёртка `components/Tabs.tsx` — `TabsRoot` / `TabsContent`):

| Вкладка | Query `?tab=` | Содержимое |
| ------- | ------------- | ---------- |
| Аккаунт | *(нет)* или `general` | Имя, раздел по умолчанию, дата/время; **Telegram** — привязка бота (`ProfileTelegramSection`, `GET/POST/DELETE /me/telegram`) |
| ИИ и capture | `models` | Модели транскрибации/summarize, имя бота capture — только если есть что настраивать |
| Безопасность | `security` | Смена пароля, TOTP 2FA (`MfaSetupPanel`) — только при локальном входе (не SSO-only) |
| Данные и API | `data` | Личный бэкап ZIP/TGZ, API-токены, удаление аккаунта |
| Интерфейс | `ui` | Быстрые действия shell: микрофон и подсказка Telegram (`PATCH /me` — `shell_show_mic`, `shell_show_telegram_link`) |

Ссылки для поддержки: `/app/profile`, `/app/profile?tab=data`, `/app/profile?tab=ui` и т.д. Неизвестная или скрытая вкладка → **Аккаунт**.

Переход с иконки Telegram в shell: `/app/profile#profile-telegram` (прокрутка к заголовку **Telegram** на **Аккаунт**; `?tab=` сбрасывается).

**Для поддержки**

- Шапка: организация / 2FA / число активных токенов / API по тарифу — сводка.
- **API-токены:** по умолчанию в списке только **активные**; «Показать отозванные (N)» раскрывает отозванные (`DELETE /auth/tokens/{id}` по-прежнему только revoke, без удаления строки в БД). При создании токена может запрашиваться TOTP при `mfa_enabled`. MCP-клиенты — OAuth `/oauth/authorize`, не personal access tokens (подсказка на странице).
- **Бэкап:** `GET /me/backup` / `POST /me/backup/restore` — как в [бэкапе библиотеки](../domain/library.md#резервная-копия-профиля).

## Быстрые действия в shell

Для участников org **`GlobalMicRecordAccess`** рисует фиксированные кнопки под топбаром (CSS `--shell-mic-top`):

| Элемент | По умолчанию | Настройка пользователя |
| ------- | ------------ | ---------------------- |
| Микрофон | Показан | Профиль → **Интерфейс** → `shell_show_mic` |
| Telegram (подсказка привязки) | Показана, пока бот включён и аккаунт не привязан | `shell_show_telegram_link`; после привязки скрывается |

**`MeTelegramProvider`** (`context/meTelegram.tsx`) один раз грузит `GET /me/telegram`, при ожидании кода опрашивает API каждые 3 с (`sessionStorage` `idigest:telegram-link-awaiting` переживает F5) и синхронно обновляет иконку в shell, блок Telegram в профиле и чекбокс на вкладке **Интерфейс**. Настройка бота на инстансе — [README — Telegram-бот](../../../README.ru.md#telegram-бот-instance-admin).

## Ingest на Library

Import / capture по URL на **LibraryPage** передаёт опциональные **`user_tags`** через `importRequest` / `captureRequest` (`pipeline.ts`). Доп. теги редактируются в **`IngestExtraTagsMultiSelect`** (модалка: pick / add / chips как на карточках объектов). Выбор хранится в `localStorage` (`ingestExtraTags.ts`) до успешного import/capture.

**Pipeline** (`IngestPipelinePanel`, `loadPipeline` / `normalizePipeline` в `pipeline.ts`): опциональный auto-transcribe и **один** skill для summarize (`SummarizeSkillRadioGroup`, есть строка «только transcribe»). Настройки — `idigest-ingest-pipeline`; summarize на transcript — `idigest-summarize-skills`. См. [Library — pipeline ingest](../domain/library.md#pipeline-ingest-ui-library).

## i18n

Три UI locale: `en`, `ru`, `es`. Language switcher записывает preference через PATCH `/me` + i18next change.

## Сборка и проверки

```bash
cd web
npm run dev        # HMR; proxy /api
npm run build      # tsc + vite → dist/
npm run lint       # oxlint
npm run test       # vitest (например auth route helpers)
npm run check:ui   # guard миграции UI (TSX + index.css, legacy-классы, submit-паттерны, cap badge)
npm run generate:api   # обновить openapi.json + schema.gen.ts (после изменений API)
```

Подробности `check:ui`: `web/scripts/check-ui-migration.mjs` и общий `ui-migration-rules.mjs` (комментарии в начале файлов). Vitest: `legacyUiGuard.test.ts` (те же guard'ы, что CI), `typesetUi.test.ts` (контракт Geist/typeset в CSS), `typography.test.ts`, `mfa.test.ts`, `pipeline.test.ts` (тела import/capture и normalize pipeline).

Assets попадают в `web/dist/assets/` — монтируются на `/assets` через FastAPI.

## Связанные страницы

- [Development setup](setup.md)
- [Backend layout](backend.md)
- [Auth API](../api/auth.md)
