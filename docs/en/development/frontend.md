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
│   ├── Verify2faPage, Enroll2faPage   # Login challenge + forced enrollment
│   ├── LibraryPage, AudioPage, TranscriptPage, SummaryPage
│   ├── TasksPage, TaskPage
│   ├── SkillsPage, SkillPage
│   ├── OrgPage, StatsPage
│   ├── InstancePage
│   ├── SsoLoginPage
│   └── ProfilePage, ChangePasswordPage, ...
├── mfa.ts              # sessionStorage helpers for login challenge_id
└── components/
    ├── Shell.tsx         # Nav layout
    ├── AppBrand.tsx
    ├── LanguageSwitcher.tsx
    ├── MfaSetupPanel.tsx # QR setup, confirm, recovery codes
    ├── ShareDialog.tsx   # Recipients list + revoke
    ├── InlineRename.tsx  # Transcript/summary/skill titles
    └── OrgLedgerModal.tsx # Instance admin wallet ledger
```

## Routing

Browser routes under `/app/*` (protected). Public: `/`, `/login`, `/signup`, `/setup`, `/forgot`, `/reset`, `/verify-2fa`, `/enroll-2fa`, `/sso/:orgId`.

`resolveHomePath(me)` in `routes.ts` picks landing page from user `default_route` and role.

## API client

`api.ts` uses `fetch` with `credentials: 'include'` for cookie auth. Same origin in production; Vite proxy in dev.

Errors expect `{ status: "error", error: { code, message } }`. API failures show as top-right toast notifications (`sonner` via `util.tsx` `showError`).

## Auth flow

1. `GET /me` on load
2. Redirect to `/login` if 401
3. `resolveAuthBlockPath(me)` in `routes.ts`:
   - `must_change_password` → `/change-password`
   - `mfa_enrollment_required` → `/enroll-2fa` (org policy; setup via `MfaSetupPanel`)
4. Login with 2FA: `POST /auth/login` returns `mfa_required` → store `challenge_id` in `sessionStorage` (`mfa.ts`) → `/verify-2fa` → `POST /auth/mfa/verify` or `/recover`
5. After login / password change / 2FA verify or enroll → `resolveAuthContinuationPath(me)` → home
6. Instance admin without org → Instance UI

Profile → Security: optional 2FA enable/disable. API token dialog prompts for TOTP when `mfa_enabled`. Org admin: `mfa_required` toggle and member reset-MFA on Org page. Profile also overrides transcription and summarize models (`PATCH /me`); Instance → Workers delete/edit opens `WorkerImpactModal` when a model or Jitsi map would be lost.

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
