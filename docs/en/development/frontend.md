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
├── types.ts          # Domain types; many alias OpenAPI via openapi/contracts.ts
├── openapi/          # Generated schema + hand-maintained aliases (see below)
├── i18n.ts           # i18next setup
├── locales/          # en.json, ru.json, es.json
├── pages/
│   ├── LandingPage, LoginPage, SignupPage, SetupPage, SsoLoginPage
│   ├── Verify2faPage, Enroll2faPage, ChangePasswordPage, ForgotPage, ResetPage
│   ├── AcceptAgreementPage, LegalDocumentPage
│   ├── LibraryPage, AudioPage, TranscriptPage, SummaryPage, PublicLinksPage
│   ├── TasksPage, TaskPage, SkillsPage, SkillPage
│   ├── OrgPage, StatsPage, ProfilePage (+ `pages/profile/*` tabs), PublicSummaryPage (guest)
│   ├── instance/     # InstancePage + tabs (workers, tariffs, orgs, …)
│   └── security/     # SecurityPage (encryption, audit log)
├── mfa.ts            # sessionStorage helpers for login challenge_id
├── context/
│   └── meTelegram.tsx        # Shared /me/telegram status + link polling
├── shell/
│   ├── constants.ts          # PROFILE_TELEGRAM_SECTION_ID (profile hash anchor)
│   └── telegramPrompt.ts     # When to show shell Telegram icon
└── components/
    ├── ui/           # shadcn primitives
    ├── app/          # AppField, AppFormActions, AdminDataTable, …
    ├── auth/         # Auth card/field chrome
    ├── Shell.tsx     # Nav layout; MeTelegramProvider wrapper
    ├── GlobalMicRecordAccess.tsx  # Floating mic + Telegram link prompt
    ├── TelegramIcon.tsx
    ├── AdminSection.tsx
    ├── MicrophoneRecordModal.tsx   # Library mic capture → POST /audios
    ├── IngestExtraTagsMultiSelect.tsx  # Library URL ingest: extra tags modal → user_tags on import/capture
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

## API types (OpenAPI)

The UI keeps TypeScript in sync with the backend contract:

| Artifact | Role |
| -------- | ---- |
| `web/openapi/openapi.json` | Committed OpenAPI snapshot (export script, not live server) |
| `web/src/openapi/schema.gen.ts` | Generated `components` / `paths` (`openapi-typescript`) |
| `web/src/openapi/contracts.ts` | `Schema*` aliases and list envelopes; import from `../openapi` in pages |
| `web/src/types.ts` | App-facing names (`Me`, `Task`, `Org`, …); re-exports OpenAPI where aligned |

After changing backend `response_model` or routes:

```bash
cd web
npm run generate:api    # export_openapi.py + generate:api-types
```

In new or touched code, prefer `api<SchemaFooResponse>(…)` over inline `api<{ … }>(…)`. List pages that merge OpenAPI list payloads with extra UI fields (e.g. `ShareBadge`) use helpers in `contracts.ts`. `Me` stays a small hybrid over `SchemaMeResponse` for prefs and legal acceptance.

Regeneration is covered in CI indirectly via pytest (`tests/test_export_openapi.py`) and `npm run build`.

## Auth flow

1. `GET /me` on load
2. Redirect to `/login` if 401
3. `resolveAuthBlockPath(me)` in `routes.ts`:
   - `must_change_password` → `/change-password`
   - `mfa_enrollment_required` → `/enroll-2fa` (org policy; setup via `MfaSetupPanel`)
4. Login with 2FA: `POST /auth/login` returns `mfa_required` → store `challenge_id` in `sessionStorage` (`mfa.ts`) → `/verify-2fa` → `POST /auth/mfa/verify` or `/recover`
5. After login / password change / 2FA verify or enroll → `resolveAuthContinuationPath(me)` → home
6. Instance admin without org → Instance UI

Profile settings use the same APIs as before (`PATCH /me`, `/auth/tokens`, `/me/backup`, …); only the UI layout changed. Org admin: `mfa_required` and member reset-MFA stay on **Org** page. Instance → Workers / Tariffs impact modals unchanged (`WorkerImpactModal`, `TariffImpactModal`).

## Profile page (`/app/profile`)

Entry: `web/src/pages/ProfilePage.tsx`; tab panels and form logic under `web/src/pages/profile/` (`useProfilePageModel` + `ProfilePageProvider`).

**Tabs** (shadcn `Tabs`, bar via `components/Tabs.tsx` — `TabsRoot` / `TabsContent`):

| Tab | Query `?tab=` | Contents |
| --- | ------------- | -------- |
| Account | *(omit)* or `general` | Name, default route after login, date/time; **Telegram** bot linking (`ProfileTelegramSection`, `GET/POST/DELETE /me/telegram`) |
| AI & capture | `models` | Transcription, summarize, capture bot overrides — shown only if the user has something to configure |
| Security | `security` | Password change, TOTP 2FA (`MfaSetupPanel`) — only for local auth (not SSO-only) |
| Data & API | `data` | Personal backup ZIP/TGZ, API tokens, delete account |
| Interface | `ui` | Shell quick actions: show/hide floating mic and Telegram link prompt (`PATCH /me` `shell_show_mic`, `shell_show_telegram_link`) |

Deep links for support: `/app/profile`, `/app/profile?tab=data`, `/app/profile?tab=ui`, etc. Unknown or hidden tab values fall back to **Account**.

Telegram deep link from the shell icon: `/app/profile#profile-telegram` (hash scrolls to the **Telegram** heading on **Account**; any `?tab=` query is cleared).

**Support notes**

- Header card: org / 2FA / active token count / API tariff — read-only summary.
- **API tokens:** list shows **active** tokens by default; link **Show revoked (N)** reveals revoked rows (still `DELETE /auth/tokens/{id}` = revoke only; no server-side purge). Creating a token may prompt for TOTP when `mfa_enabled`. MCP/OAuth clients use `/oauth/authorize`, not personal access tokens (hint on the page).
- **Backup:** `GET /me/backup` / `POST /me/backup/restore` — same as [Library backup](../domain/library.md#profile-backup).

## App shell quick actions

For org members, **`GlobalMicRecordAccess`** renders fixed buttons under the top bar (CSS `--shell-mic-top`):

| Control | Default | User override |
| ------- | ------- | ------------- |
| Microphone | Shown | Profile → **Interface** → `shell_show_mic` |
| Telegram (link prompt) | Shown while bot enabled and account not linked | `shell_show_telegram_link`; hidden automatically after link |

**`MeTelegramProvider`** (`context/meTelegram.tsx`) loads `GET /me/telegram` once per session, polls every 3s while a link code is pending (`sessionStorage` `idigest:telegram-link-awaiting` survives refresh), and updates the shell icon, profile Telegram block, and Interface tab checkbox together. Instance bot setup remains in [README — Telegram bot](../../../README.md#telegram-bot-instance-admin).

## Library ingest

URL / meeting import on **LibraryPage** sends optional **`user_tags`** via `importRequest` / `captureRequest` (`pipeline.ts`). Extra tag names are edited in **`IngestExtraTagsMultiSelect`** (modal with the same pick / add / chip pattern as object tag editors). Last choice is stored in `localStorage` (`ingestExtraTags.ts`) until a successful import or capture clears it.

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
npm run generate:api   # refresh openapi.json + schema.gen.ts (after backend API changes)
```

Assets emit to `web/dist/assets/` — mounted at `/assets` by FastAPI.

## Related pages

- [Development setup](setup.md)
- [Backend layout](backend.md)
- [Auth API](../api/auth.md)
