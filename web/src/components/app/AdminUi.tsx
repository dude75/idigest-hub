import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AppHoverHint } from '@/components/app/AppHoverHint'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { AppFormActions as AppFormActionsBase, AppSubmitButton } from './AppFormActions'

export { AppSubmitButton }

/** Legacy `.badge` tones mapped to shadcn Badge. */
export type HubBadgeTone = 'primary' | 'success' | 'warning' | 'pending' | 'muted'

const hubBadgeClass: Record<HubBadgeTone, string> = {
  primary: '',
  success:
    'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100',
  warning: '',
  pending:
    'border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100',
  muted: 'text-muted-foreground',
}

const hubBadgeVariant: Record<
  HubBadgeTone,
  'default' | 'secondary' | 'destructive' | 'outline'
> = {
  primary: 'default',
  success: 'outline',
  warning: 'destructive',
  pending: 'outline',
  muted: 'outline',
}

export function HubBadge({
  tone = 'primary',
  className,
  title,
  children,
}: {
  tone?: HubBadgeTone
  className?: string
  title?: string
  children: ReactNode
}) {
  const badge = (
    <Badge variant={hubBadgeVariant[tone]} className={cn(hubBadgeClass[tone], className)}>
      {children}
    </Badge>
  )
  if (!title) {
    return badge
  }
  return <AppHoverHint content={title}>{badge}</AppHoverHint>
}

/** Maps legacy `.badge` modifier classes to HubBadge tones. */
export function hubBadgeToneFromLegacy(className?: string): HubBadgeTone {
  if (!className) return 'primary'
  if (className.includes('warn') || className.includes('err')) return 'warning'
  if (className.includes('wait')) return 'pending'
  if (className.includes('out')) return 'success'
  return 'primary'
}

export function HubBadgeLink({
  to,
  tone = 'success',
  className,
  children,
}: {
  to: string
  tone?: HubBadgeTone
  className?: string
  children: ReactNode
}) {
  return (
    <Link to={to} className={cn('inline-flex no-underline hover:no-underline', className)}>
      <HubBadge tone={tone}>{children}</HubBadge>
    </Link>
  )
}

export function AdminRowActions({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-nowrap items-center justify-end gap-1.5', className)}>{children}</div>
  )
}

export function AdminFormActions({ children, className }: { children: ReactNode; className?: string }) {
  return <AppFormActionsBase className={cn('pt-1', className)}>{children}</AppFormActionsBase>
}

export function AdminMetaRow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-wrap items-center gap-1.5', className)}>{children}</div>
  )
}
