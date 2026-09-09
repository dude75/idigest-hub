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
│   ├── LibraryPage, AudioPage, TranscriptPage, SummaryPage
│   ├── TasksPage, TaskPage
│   ├── SkillsPage, SkillPage
│   ├── OrgPage, StatsPage
│   ├── InstancePage
│   ├── SsoLoginPage
│   └── ProfilePage, ChangePasswordPage, ...
└── components/
    ├── Shell.tsx         # Nav layout
    ├── AppBrand.tsx
    ├── LanguageSwitcher.tsx
    ├── ShareDialog.tsx   # Список получателей + отзыв
    ├── InlineRename.tsx  # Заголовки transcript/summary/skill
    └── OrgLedgerModal.tsx # Ledger кошелька в instance admin
```

## Routing

Browser routes под `/app/*` (protected). Public: `/`, `/login`, `/signup`, `/setup`, `/forgot`, `/reset`, `/sso/:orgId`.

`resolveHomePath(me)` в `routes.ts` выбирает landing page из user `default_route` и role.

## API client

`api.ts` использует `fetch` с `credentials: 'include'` для cookie auth. Same origin в production; Vite proxy в dev.

Errors ожидают `{ status: "error", error: { code, message } }`. Ошибки API показываются toast-уведомлениями справа сверху (`sonner` через `util.tsx` `showError`).

## Auth flow

1. `GET /me` при загрузке
2. Redirect на `/login` при 401
3. `must_change_password` → force `/change-password`
4. Instance admin без org → Instance UI

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
