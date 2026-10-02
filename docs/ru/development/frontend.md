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

Новые экраны собирайте из **shadcn-примитивов** и **App\***, без legacy global CSS (`.btn`, `.card`, произвольный `.stack`). Primary save/create — общий паттерн submit-кнопки; CI проверяет через `npm run check:ui` (`web/scripts/check-ui-migration.mjs`, в GitLab CI вместе с `npm test` и `npm run build`).

## Дерево исходников (обзор)

```
web/src/
├── main.tsx          # Entry
├── App.tsx           # Router shell, auth gates
├── auth.tsx          # Session context, login state
├── api.ts            # fetch wrappers for /api/v1
├── routes.ts         # Path helpers, default_route logic
├── types.ts          # Me, Task, entities
├── i18n.ts           # i18next setup
├── locales/          # en.json, ru.json, es.json
├── pages/
│   ├── LandingPage, LoginPage, SignupPage, SetupPage, SsoLoginPage
│   ├── Verify2faPage, Enroll2faPage, ChangePasswordPage, ForgotPage, ResetPage
│   ├── AcceptAgreementPage, LegalDocumentPage
│   ├── LibraryPage, AudioPage, TranscriptPage, SummaryPage, PublicLinksPage
│   ├── TasksPage, TaskPage, SkillsPage, SkillPage
│   ├── OrgPage, StatsPage, ProfilePage, PublicSummaryPage (guest)
│   ├── instance/     # InstancePage + вкладки (workers, tariffs, orgs, …)
│   └── security/     # SecurityPage (encryption, audit log)
├── mfa.ts            # sessionStorage helpers для login challenge_id
└── components/
    ├── ui/           # shadcn primitives
    ├── app/          # AppField, AppFormActions, AdminDataTable, …
    ├── auth/         # Auth card/field chrome
    ├── Shell.tsx     # Nav layout
    ├── AdminSection.tsx
    ├── MicrophoneRecordModal.tsx   # Запись с микрофона → POST /audios
    ├── ShareDialog.tsx, MfaSetupPanel.tsx, …
    └── …
```

`InstancePage` и тяжёлые admin-вкладки подгружаются lazy, чтобы не раздувать основной бандл.

## Routing

Public: `/`, `/login`, `/signup`, `/setup`, `/forgot`, `/reset`, `/verify-2fa`, `/enroll-2fa`, `/change-password`, `/accept-agreement`, `/sso/:orgId`, `/public/summary/:token`, `/legal/:slug`.

Приложение: `/app/*` (library с `:tab`, детали audio/transcript/summary, skills, org, stats, profile, tasks, instance, security, public-links).

`resolveHomePath(me)` в `routes.ts` выбирает landing page из user `default_route` и role.

## API client

`api.ts` использует `fetch` с `credentials: 'include'` для cookie auth. Same origin в production; Vite proxy в dev (см. [setup](setup.md) про `HUB_PORT`).

Errors ожидают `{ status: "error", error: { code, message } }`. Ошибки API показываются toast-уведомлениями справа сверху (`sonner` через `util.tsx` `showError`).

## Auth flow

1. `GET /me` при загрузке
2. Redirect на `/login` при 401
3. `resolveAuthBlockPath(me)` в `routes.ts`:
   - `must_change_password` → `/change-password`
   - `mfa_enrollment_required` → `/enroll-2fa` (политика org; setup через `MfaSetupPanel`)
4. Login с 2FA: `POST /auth/login` возвращает `mfa_required` → `challenge_id` в `sessionStorage` (`mfa.ts`) → `/verify-2fa` → `POST /auth/mfa/verify` или `/recover`
5. После login / смены пароля / verify или enroll 2FA → `resolveAuthContinuationPath(me)` → home
6. Instance admin без org → Instance UI

Profile → Security: опциональное включение/отключение 2FA. Диалог API token запрашивает TOTP при `mfa_enabled`. Org admin: переключатель `mfa_required` и reset-MFA участников на Org page. В Profile также переопределяются модели транскрибации и summarize и опциональное имя бота capture (`PATCH /me`); удаление и правка в Instance → Workers открывают `WorkerImpactModal`, если пропадёт модель или connector capture (карты Jitsi host org не привязаны к воркерам). Удаление в Instance → Tariffs открывает `TariffImpactModal`: список org на тарифе и опциональный перенос на другой активный тариф перед DELETE.

## i18n

Три UI locale: `en`, `ru`, `es`. Language switcher записывает preference через PATCH `/me` + i18next change.

## Сборка и проверки

```bash
cd web
npm run dev        # HMR; proxy /api
npm run build      # tsc + vite → dist/
npm run lint       # oxlint
npm run test       # vitest (например auth route helpers)
npm run check:ui   # guard скрипт миграции UI
```

Assets попадают в `web/dist/assets/` — монтируются на `/assets` через FastAPI.

## Связанные страницы

- [Development setup](setup.md)
- [Auth API](../api/auth.md)
