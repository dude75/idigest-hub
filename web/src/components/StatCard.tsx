import type { ReactNode } from 'react'
import { AppHoverHint } from '@/components/app/AppHoverHint'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
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
  /** Hover hint; also shown as muted footer line when set */
  title?: string
  /** Optional second footer line (dashboard-01 style) */
  footer?: ReactNode
  tone?: StatTone
  valueClassName?: string
}

export function StatCard({
  label,
  value,
  unit,
  title,
  footer,
  tone = 'default',
  valueClassName,
}: StatCardProps) {
  const valueClass = [
    valueClassName,
    tone.startsWith('proxy-') ? `stat-proxy-${tone.slice(6)}` : '',
  ]
    .filter(Boolean)
    .join(' ')

  const card = (
    <Card
      className={cn(
        '@container/card stat-card font-sans bg-gradient-to-t from-primary/5 to-card shadow-xs dark:bg-card dark:bg-none',
        (title || footer) && 'cursor-help',
      )}
    >
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        {unit ? (
          <CardAction>
            <Badge variant="outline">{unit}</Badge>
          </CardAction>
        ) : null}
        <CardTitle className={cn('font-semibold leading-none', valueClass)}>
          {value}
        </CardTitle>
      </CardHeader>
      {footer || title ? (
        <CardFooter className="flex-col items-start gap-1.5 border-t-0 bg-transparent px-(--card-spacing) pt-0 pb-(--card-spacing) text-sm">
          {footer ? <div className="line-clamp-1 font-medium">{footer}</div> : null}
          {title ? <div className="text-muted-foreground">{title}</div> : null}
        </CardFooter>
      ) : null}
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
