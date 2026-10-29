import { cn } from '@/lib/utils'

/**
 * App chrome typography (Tailwind). Prefer these over inline `text-muted-foreground`
 * or legacy CSS `.muted` — see `npm run check:ui` and `typography.test.ts`.
 * OAuth server HTML uses `auth-shell.css` `.muted` instead (not this module).
 */

/** Primary line in admin tables and list rows (16px / medium). */
export const appPrimaryText = 'text-base font-medium text-foreground'

/** Secondary / meta lines under titles and in table muted cells. */
export const appMutedText = 'text-sm text-muted-foreground'

/** Numeric table cells (sans tabular nums — not mono). */
export const appNumericText = 'tabular-nums'

export const appListRowTitle = cn(
  appPrimaryText,
  'min-w-0 leading-snug',
  '[&:is(a)]:transition-colors [&:is(a)]:hover:text-primary',
)

export const appListRowMeta = cn(
  'mt-1.5 flex flex-wrap items-center gap-x-1 gap-y-0.5 text-sm leading-normal text-muted-foreground',
  '[&_a:not([data-slot=button])]:font-medium',
  '[&_a:not([data-slot=button])]:text-muted-foreground',
  '[&_a:not([data-slot=button])]:underline-offset-4',
  '[&_a:not([data-slot=button])]:hover:text-foreground',
  '[&_a:not([data-slot=button])]:hover:underline',
)

/** Human-readable durations in meta rows and ledger (i18n via AppDuration). */
export const appDurationHumanClass = cn(appMutedText, appNumericText)

/** Compact clock durations in stats and charts (MM:SS). */
export const appDurationCompactClass = cn(appNumericText, 'text-muted-foreground')

/** Entity detail page main heading. */
export const appEntityTitle =
  'mb-4 text-[1.35rem] font-semibold leading-tight tracking-tight text-foreground'

/** Ingest studio / nested panel headings. */
export const appPanelTitle = 'mb-1 text-[1.05rem] font-semibold leading-snug text-foreground'

/** Stats chart section eyebrows. */
export const appChartEyebrow =
  'mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground'

/** Source group headings in library lists. */
export const appGroupTitle = cn(
  appPrimaryText,
  '[&_a]:transition-colors [&_a]:hover:text-primary',
)

/** Public link / share meta definition lists. */
export const appMetaDl =
  'm-0 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-muted-foreground'
export const appMetaDlTerm = 'font-medium whitespace-nowrap'
export const appMetaDlValue = cn(appNumericText, 'min-w-0 whitespace-nowrap')

export const appPipelineStepLabel = 'text-sm text-muted-foreground'

export function appPipelineStepLabelClass(
  status: 'pending' | 'waiting' | 'active' | 'done',
): string {
  switch (status) {
    case 'active':
      return cn(appPipelineStepLabel, 'font-semibold text-foreground')
    case 'done':
      return cn(appPipelineStepLabel, 'text-foreground')
    case 'waiting':
      return cn(appPipelineStepLabel, 'font-medium text-[var(--warn-ink)]')
    default:
      return appPipelineStepLabel
  }
}

/** Secondary text at inherited size (Tailwind token, not legacy `.muted` CSS). */
export const appMuted = 'text-muted-foreground'

/** Section / card lead copy under titles. */
export const appAdminLead = cn(appMutedText, 'm-0 text-base')

/** Profile section description beside heading. */
export const appProfileSectionLead = cn(
  appMutedText,
  'm-0 min-w-0 flex-[1_1_12rem] leading-snug',
)

/** Entity detail meta (date, source links, badges). */
export const appEntityMetaRow = cn(
  'flex flex-wrap items-center gap-2',
  appMutedText,
  '[&_a:not([data-slot=button])]:font-medium',
  '[&_a:not([data-slot=button])]:text-muted-foreground',
  '[&_a:not([data-slot=button])]:underline-offset-4',
  '[&_a:not([data-slot=button])]:hover:text-foreground',
  '[&_a:not([data-slot=button])]:hover:underline',
)

/** Small captions on share / form labels. */
export const appFieldCaption = 'text-xs font-normal text-muted-foreground'

/** Compact metric / stat labels (profile header, etc.). */
export const appMetricLabel = cn(appFieldCaption, 'font-medium')

/** Marketing hero lead (slightly larger than appAdminLead). */
export const appLandingLead = cn(
  appMuted,
  'm-0 mb-6 max-w-[34rem] text-[1.08rem] leading-[1.55]',
)

/** Hero kicker above the headline (accent uppercase). */
export const appLandingEyebrow = cn(
  'm-0 mb-[0.65rem] text-[0.82rem] font-semibold uppercase tracking-wide text-[var(--hub-accent)]',
)

/** Trust band section title. */
export const appLandingTrustCaption = cn(appMuted, 'm-0 mb-[0.85rem] text-[0.85rem]')

/** Uppercase eyebrows in tone analytics chips. */
export const appToneEyebrow = cn(appFieldCaption, 'font-semibold uppercase tracking-wide')

/** Secondary row labels in worker/tariff impact modals. */
export const appImpactRowLabel = cn(appMuted, 'text-[0.8rem] whitespace-nowrap')

/** Muted count chips (queued / running / idle). */
export const appImpactTagMuted = cn(appMuted, 'text-[0.72rem] leading-[1.2]')

/** Landing step / feature / FAQ body copy. */
export const appLandingCardBody = cn(appMuted, 'm-0 text-[0.92rem] leading-normal')

/** Empty states in stats tables and admin sections. */
export const appStatsEmpty = cn(appMuted, 'm-0 px-2 py-6 text-center text-[0.9rem]')

/** List row card chrome (replaces legacy `.item` / `.row`). */
export const listRowChrome = cn(
  'flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-[var(--line)] bg-card px-[0.85rem] py-[0.7rem]',
)

/** Landing tariff quota footnotes under pricing cards. */
export const appPricingQuotaNote = cn(appMutedText, 'm-0 mt-[0.45rem] text-[0.82rem] leading-snug')

/** Vertical form stacks (replaces legacy `.stack` in CSS). */
export const appFormStack =
  'grid gap-[0.65rem] [&>[data-slot=button]]:justify-self-start [&>[data-slot=button]]:w-auto [&>[data-slot=button]]:max-w-full'

/** Share panel inner grid — tighter gap, full-width action buttons. */
export const appSharePanelStack = cn(
  appFormStack,
  'gap-[0.45rem] [&>.share-panel-action-block[data-slot=button]]:justify-self-stretch [&>.share-panel-action-block[data-slot=button]]:w-full',
)

/** Org / instance settings sections (keeps `org-settings-stack` for admin-page spacing). */
export const appSettingsStack = 'org-settings-stack flex flex-col gap-4'

/** Login email/SSO panels occupy the same grid cell. */
export const appAuthPanelStack = cn(
  'grid login-mode-panels',
  '[&>.auth-panel]:col-start-1 [&>.auth-panel]:row-start-1 [&>.auth-panel]:min-w-0',
  '[&>.auth-panel[aria-hidden=true]]:invisible [&>.auth-panel[aria-hidden=true]]:pointer-events-none [&>.auth-panel[aria-hidden=true]]:select-none',
)

/** Share dialog section headings. */
export const appShareSectionHead = 'm-0 text-[0.9rem] font-semibold text-foreground'

/** Profile backup / MFA one-time secret headings. */
export const appProfileSecretTitle = 'm-0 mb-[0.55rem] text-[0.9rem] font-semibold leading-snug text-foreground'

/** Instance org detail subheadings (users table, etc.). */
export const appDetailSubheading = 'm-0 text-[0.8rem] font-semibold text-foreground'

/** Transcript tone summary title (inline metrics row). */
export const appTranscriptToneTitleInline = 'text-[0.8125rem] font-semibold text-foreground'

/** Transcript tone block title (full card header). */
export const appTranscriptToneTitle =
  'm-0 text-[0.9375rem] font-semibold leading-snug text-foreground'

/** Worker/tariff impact modal note rows. */
export const appImpactNote = cn(appMutedText, 'text-[0.82rem]')

/** App shell / auth topbar nav links (inactive state). */
export const appChromeNavLink = cn(
  appMuted,
  'rounded-md px-2 py-1 text-[0.9rem] no-underline',
  'hover:bg-card hover:text-foreground hover:shadow-sm',
  '[&.active]:bg-card [&.active]:text-foreground [&.active]:shadow-sm',
)
