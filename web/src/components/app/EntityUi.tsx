import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { ButtonLink } from '@/components/ui/button-link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { AdminTableCard } from '../AdminSection'

type EntityPageProps = {
  children: ReactNode
  className?: string
  backTo?: string
}

const ENTITY_BACK_ANCHOR =
  '.entity-detail-card, .entity-body-card, .admin-table-card, .transcript-summaries'

/** Member entity pages (audio, transcript, summary, skill). */
export function EntityPage({ children, className, backTo }: EntityPageProps) {
  const { t } = useTranslation()
  const layoutRef = useRef<HTMLDivElement>(null)
  const mainRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!backTo) return
    const layout = layoutRef.current
    const main = mainRef.current
    if (!layout || !main) return

    const sync = () => {
      const block = main.querySelector(ENTITY_BACK_ANCHOR)
      if (!block) {
        layout.style.setProperty('--entity-back-offset', '0px')
        return
      }
      const mainTop = main.getBoundingClientRect().top
      const blockTop = block.getBoundingClientRect().top
      layout.style.setProperty('--entity-back-offset', `${Math.max(0, Math.round(blockTop - mainTop))}px`)
    }

    sync()
    window.addEventListener('resize', sync)
    return () => {
      window.removeEventListener('resize', sync)
    }
  }, [backTo, children])

  if (!backTo) {
    return <div className={cn('entity-page', className)}>{children}</div>
  }
  return (
    <div className={cn('entity-page', className)}>
      <div ref={layoutRef} className="entity-page-layout">
        <EntityBackLink to={backTo} aria-label={t('common.back')} />
        <div ref={mainRef} className="entity-page-main">
          {children}
        </div>
      </div>
    </div>
  )
}

export function EntityBackLink({ to, 'aria-label': ariaLabel }: { to: string; 'aria-label': string }) {
  return (
    <ButtonLink
      to={to}
      variant="outline"
      size="icon"
      className="entity-back size-9 shrink-0 rounded-full bg-card shadow-xs transition-none"
      aria-label={ariaLabel}
    >
      <ArrowLeft className="size-4" aria-hidden />
    </ButtonLink>
  )
}

export function EntityDetailCard({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <Card className={cn('entity-detail-card', className)}>
      <CardContent className="flex flex-col gap-3 pt-6">{children}</CardContent>
    </Card>
  )
}

type EntityBodyCardProps = {
  title: string
  children: ReactNode
  className?: string
  actions?: ReactNode
}

export function EntityBodyCard({ title, children, className, actions }: EntityBodyCardProps) {
  return (
    <Card className={cn('entity-body-card', className)}>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 space-y-0 pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
        {actions}
      </CardHeader>
      <CardContent className="pt-0">{children}</CardContent>
    </Card>
  )
}

type ListSectionProps = {
  title?: string
  lead?: string
  empty?: string
  isEmpty?: boolean
  actions?: ReactNode
  children: ReactNode
  footer?: ReactNode
  className?: string
  /** List only — no nested Card (e.g. library panel). */
  embedded?: boolean
}

/** Flush list inside shadcn Card (tasks, library, entity related lists). */
export function ListSection({
  title,
  lead,
  empty,
  isEmpty,
  actions,
  children,
  footer,
  className,
  embedded = false,
}: ListSectionProps) {
  if (embedded) {
    return (
      <section className={cn('library-list-embedded', className)}>
        {title || actions ? (
          <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border px-4 py-3 sm:px-6">
            {title ? <h2 className="text-sm font-medium text-foreground">{title}</h2> : <span />}
            {actions ? <div className="flex flex-wrap items-end gap-3">{actions}</div> : null}
          </div>
        ) : null}
        {isEmpty && empty ? (
          <p className="stats-empty px-6 py-10 text-center text-sm text-muted-foreground">{empty}</p>
        ) : (
          <div className="list task-list-embedded">{children}</div>
        )}
        {footer}
      </section>
    )
  }

  return (
    <AdminTableCard
      title={title}
      lead={lead}
      empty={empty}
      isEmpty={isEmpty}
      tableLayout={!isEmpty}
      actions={actions}
      className={className}
    >
      {!isEmpty ? <div className="list task-list-embedded">{children}</div> : null}
      {footer}
    </AdminTableCard>
  )
}
