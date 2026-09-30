import type { ReactNode } from 'react'
import { AppHoverHint } from '@/components/app/AppHoverHint'
import { Card, CardContent, CardDescription } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export type StatTone =
  | 'default'
  | 'transcribe'
  | 'summarize'
  | 'audio'
  | 'chars'
  | 'amount'
  | 'ops'
  | 'proxy-up'
  | 'proxy-down'
  | 'proxy-na'

type StatCardProps = {
  label: string
  value: ReactNode
  unit?: string
  title?: string
  tone?: StatTone
  valueClassName?: string
}

export function StatCard({ label, value, unit, title, tone = 'default', valueClassName }: StatCardProps) {
  const valueClass = ['stat-value', valueClassName, tone.startsWith('proxy-') ? `stat-proxy-${tone.slice(6)}` : '']
    .filter(Boolean)
    .join(' ')

  const card = (
    <Card className={cn('stat stat-card min-h-[5.25rem] py-4 shadow-none', `stat-${tone}`, title && 'cursor-help')}>
      <CardContent className="flex h-full flex-col px-4 py-0">
        <CardDescription className="stat-label m-0">{label}</CardDescription>
        <div className="stat-body">
          <div className={valueClass}>{value}</div>
          {unit ? <div className="stat-unit">{unit}</div> : null}
        </div>
      </CardContent>
    </Card>
  )

  if (!title) {
    return card
  }

  return (
    <AppHoverHint content={title} className="block h-full w-full min-w-0">
      {card}
    </AppHoverHint>
  )
}

type StatGridProps = {
  children: ReactNode
}

export function StatGrid({ children }: StatGridProps) {
  return (
    <div className="stat-block">
      <div className="stat-grid">{children}</div>
    </div>
  )
}
