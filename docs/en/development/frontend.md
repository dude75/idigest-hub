# Frontend layout

React 19 + TypeScript + Vite. Source: `web/src/`. Package README: [web/README.md](../../../web/README.md).

## UI stack

| Layer | Location / package |
| ----- | ------------------- |
| shadcn (style `base-nova`) | `web/components.json`, CLI package `shadcn` |
| Primitives | `web/src/components/ui/` (Base UI + Tailwind) |
| App wrappers | `web/src/components/app/` — forms, admin tables, shared controls |
| Icons | `lucide-react` (`iconLibrary: lucide` in `components.json`) |
| Font | Geist via `@fontsource-variable/geist` in `index.css` |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`) |
| Notifications | `sonner` (`showError` / toasts in `util.tsx`) |

New screens should compose **shadcn primitives** and **App\*** wrappers, not legacy global CSS (`.btn`, `.card`, ad-hoc `.stack`). Primary save/create actions use the shared submit button pattern enforced by `npm run check:ui` (`web/scripts/check-ui-migration.mjs`, runs in GitLab CI with `npm test` and `npm run build`).

## Source tree (overview)

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
│   ├── instance/     # InstancePage + tabs (workers, tariffs, orgs, …)
│   └── security/     # SecurityPage (encryption, audit log)
├── mfa.ts            # sessionStorage helpers for login challenge_id
└── components/
    ├── ui/           # shadcn primitives
    ├── app/          # AppField, AppFormActions, AdminDataTable, …
    ├── auth/         # Auth card/field chrome
    ├── Shell.tsx     # Nav layout
    ├── AdminSection.tsx
    ├── MicrophoneRecordModal.tsx   # Library mic capture → POST /audios
    ├── ShareDialog.tsx, MfaSetupPanel.tsx, …
    └── …
```

`InstancePage` and heavy admin tabs are lazy-loaded to keep the main bundle smaller.

## Routing

Public: `/`, `/login`, `/signup`, `/setup`, `/forgot`, `/reset`, `/verify-2fa`, `/enroll-2fa`, `/change-password`, `/accept-agreement`, `/sso/:orgId`, `/public/summary/:token`, `/legal/:slug`.

Authenticated app: `/app/*` (library with `:tab`, audio/transcript/summary detail, skills, org, stats, profile, tasks, instance, security, public-links).

`resolveHomePath(me)` in `routes.ts` picks the landing page from user `default_route` and role.

## API client

`api.ts` uses `fetch` with `credentials: 'include'` for cookie auth. Same origin in production; Vite proxy in dev (see [setup](setup.md) for `HUB_PORT`).

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

Profile → Security: optional 2FA enable/disable. API token dialog prompts for TOTP when `mfa_enabled`. Org admin: `mfa_required` toggle and member reset-MFA on Org page. Profile also overrides transcription, summarize models, and optional capture bot display name (`PATCH /me`); Instance → Workers delete/edit opens `WorkerImpactModal` when a model or capture connector would be lost (org Jitsi host maps are not tied to workers).

## i18n

Three UI locales: `en`, `ru`, `es`. Language switcher writes preference via PATCH `/me` + i18next change.

## Build and checks

```bash
cd web
npm run dev        # HMR; proxy /api
npm run build      # tsc + vite → dist/
npm run lint       # oxlint
npm run test       # vitest (e.g. auth route helpers)
npm run check:ui   # migration guard script
```

Assets emit to `web/dist/assets/` — mounted at `/assets` by FastAPI.

## Related pages

- [Development setup](setup.md)
- [Auth API](../api/auth.md)
