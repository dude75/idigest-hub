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
