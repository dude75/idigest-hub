import type { ReactNode } from 'react'

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

  return (
    <div className={`stat stat-${tone}`} title={title}>
      <div className="stat-label">{label}</div>
      <div className="stat-body">
        <div className={valueClass}>{value}</div>
        {unit ? <div className="stat-unit">{unit}</div> : null}
      </div>
    </div>
  )
}

type StatGridProps = {
  children: ReactNode
  caption?: ReactNode
}

export function StatGrid({ children, caption }: StatGridProps) {
  return (
    <div className="stat-block">
      {caption ? <div className="stat-caption">{caption}</div> : null}
      <div className="stat-grid">{children}</div>
    </div>
  )
}
