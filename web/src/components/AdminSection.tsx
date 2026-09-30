import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { SettingsFoldSummary } from './app/SettingsFoldSummary'

export function AdminPage({ children }: { children: ReactNode }) {
  return <div className="admin-page">{children}</div>
}

/** Replaces legacy `.card.stack` sections (filters, toolbars). */
export function AppStackCard({
  title,
  lead,
  className,
  contentClassName,
  children,
}: {
  title?: ReactNode
  lead?: ReactNode
  className?: string
  contentClassName?: string
  children: ReactNode
}) {
  return (
    <Card className={cn('admin-section-card gap-2', className)}>
      {title ? (
        <CardHeader className="pb-0">
          <CardTitle className="text-base">{title}</CardTitle>
          {lead ? <CardDescription>{lead}</CardDescription> : null}
        </CardHeader>
      ) : null}
      <CardContent className={cn('flex flex-col gap-2', !title && 'pt-6', contentClassName)}>
        {children}
      </CardContent>
    </Card>
  )
}

/** Instance/org settings `<details>` block (shadcn Card + summary row). */
export function SettingsFoldCard({
  title,
  summaryExtra,
  className,
  children,
}: {
  title: ReactNode
  summaryExtra?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <Card className={cn('org-settings-folds org-fold gap-0 overflow-hidden py-0', className)}>
      <details className="fold org-fold-section">
        <summary className="org-fold-summary">
          <SettingsFoldSummary title={title} meta={summaryExtra} />
        </summary>
        <CardContent className="flex flex-col gap-3 border-t pt-4 fold-body">{children}</CardContent>
      </details>
    </Card>
  )
}

/** Collapsible admin form block (workers/orgs create). */
export function AdminFoldCard({
  title,
  className,
  children,
  open,
  onToggle,
}: {
  title: ReactNode
  className?: string
  children: ReactNode
  open?: boolean
  onToggle?: (open: boolean) => void
}) {
  return (
    <Card className={cn('admin-fold-card', className)}>
      <details
        className="group"
        open={open}
        onToggle={(e) => onToggle?.(e.currentTarget.open)}
      >
        <summary className="cursor-pointer list-none px-6 py-4 font-medium marker:content-none [&::-webkit-details-marker]:hidden">
          {title}
        </summary>
        <CardContent className="flex flex-col gap-3 border-t pt-4">{children}</CardContent>
      </details>
    </Card>
  )
}

type AdminFormCardProps = {
  title: string
  lead?: ReactNode
  className?: string
  children: ReactNode
}

export function AdminFormCard({ title, lead, className, children }: AdminFormCardProps) {
  return (
    <Card className={cn('admin-form-card', className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {lead ? <CardDescription className="admin-lead">{lead}</CardDescription> : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">{children}</CardContent>
    </Card>
  )
}

type AdminTableCardProps = {
  title?: string
  lead?: ReactNode
  actions?: ReactNode
  className?: string
  children: ReactNode
  empty?: string
  isEmpty?: boolean
  /** shadcn card + flush table body (docs-style). */
  tableLayout?: boolean
}

export function AdminTableCard({
  title,
  lead,
  actions,
  className,
  children,
  empty,
  isEmpty,
  tableLayout = false,
}: AdminTableCardProps) {
  return (
    <Card className={cn('admin-table-card', className)}>
      {title || actions ? (
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
          <div className="min-w-0 space-y-1.5">
            {title ? <CardTitle>{title}</CardTitle> : null}
            {lead ? <CardDescription className="admin-lead">{lead}</CardDescription> : null}
          </div>
          {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
        </CardHeader>
      ) : null}
      <CardContent
        className={cn(
          tableLayout ? 'p-0' : 'flex flex-col gap-3',
          !tableLayout && !title && !actions && 'pt-6',
        )}
      >
        {isEmpty && empty ? (
          <p className={cn('stats-empty', tableLayout && 'px-6 py-8')}>{empty}</p>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  )
}
