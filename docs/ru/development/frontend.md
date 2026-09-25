# Структура frontend

React 19 + TypeScript + Vite. Source: `web/src/`

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
├── pages/            # Route components
│   ├── LandingPage, LoginPage, SignupPage, SetupPage
│   ├── Verify2faPage, Enroll2faPage   # Login challenge + принудительный enrollment
│   ├── LibraryPage, AudioPage, TranscriptPage, SummaryPage
│   ├── TasksPage, TaskPage
│   ├── SkillsPage, SkillPage
│   ├── OrgPage, StatsPage
│   ├── InstancePage
│   ├── SsoLoginPage
│   └── ProfilePage, ChangePasswordPage, ...
├── mfa.ts              # sessionStorage helpers для login challenge_id
└── components/
    ├── Shell.tsx         # Nav layout
    ├── AppBrand.tsx
    ├── LanguageSwitcher.tsx
    ├── MfaSetupPanel.tsx # QR setup, confirm, recovery codes
    ├── ShareDialog.tsx   # Список получателей + отзыв
    ├── InlineRename.tsx  # Заголовки transcript/summary/skill
    └── OrgLedgerModal.tsx # Ledger кошелька в instance admin
```

## Routing

Browser routes под `/app/*` (protected). Public: `/`, `/login`, `/signup`, `/setup`, `/forgot`, `/reset`, `/verify-2fa`, `/enroll-2fa`, `/sso/:orgId`.

`resolveHomePath(me)` в `routes.ts` выбирает landing page из user `default_route` и role.

## API client

`api.ts` использует `fetch` с `credentials: 'include'` для cookie auth. Same origin в production; Vite proxy в dev.

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

Profile → Security: опциональное включение/отключение 2FA. Диалог API token запрашивает TOTP при `mfa_enabled`. Org admin: переключатель `mfa_required` и reset-MFA участников на Org page. В Profile также переопределяются модели транскрибации и summarize и опциональное имя бота capture (`PATCH /me`); удаление и правка в Instance → Workers открывают `WorkerImpactModal`, если пропадёт модель или connector capture (карты Jitsi host org не привязаны к воркерам).

## i18n

Три UI locale: `en`, `ru`, `es`. Language switcher записывает preference через PATCH `/me` + i18next change.

## Build

```bash
cd web
npm run build    # tsc + vite → dist/
npm run lint     # oxlint
```

Assets попадают в `web/dist/assets/` — монтируются на `/assets` через FastAPI.

## Связанные страницы

- [Development setup](setup.md)
- [Auth API](../api/auth.md)
