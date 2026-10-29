import { cn } from '@/lib/utils'

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
