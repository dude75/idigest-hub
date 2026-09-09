# Frontend layout

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
    ├── ShareDialog.tsx   # Recipients list + revoke
    ├── InlineRename.tsx  # Transcript/summary/skill titles
    └── OrgLedgerModal.tsx # Instance admin wallet ledger
```

## Routing

Browser routes under `/app/*` (protected). Public: `/`, `/login`, `/signup`, `/setup`, `/forgot`, `/reset`, `/sso/:orgId`.

`resolveHomePath(me)` in `routes.ts` picks landing page from user `default_route` and role.

## API client

`api.ts` uses `fetch` with `credentials: 'include'` for cookie auth. Same origin in production; Vite proxy in dev.

Errors expect `{ status: "error", error: { code, message } }`. API failures show as top-right toast notifications (`sonner` via `util.tsx` `showError`).

## Auth flow

1. `GET /me` on load
2. Redirect to `/login` if 401
3. `must_change_password` → force `/change-password`
4. Instance admin without org → Instance UI

## i18n

Three UI locales: `en`, `ru`, `es`. Language switcher writes preference via PATCH `/me` + i18next change.

## Build

```bash
cd web
npm run build    # tsc + vite → dist/
npm run lint     # oxlint
```

Assets emitted to `web/dist/assets/` — mounted at `/assets` by FastAPI.

## Related pages

- [Development setup](setup.md)
- [Auth API](../api/auth.md)
