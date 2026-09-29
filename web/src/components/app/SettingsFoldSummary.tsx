import type { ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

type Props = {
  title: ReactNode
  meta?: ReactNode
  className?: string
}

/** Row header for org/instance settings `<details>` (title + badges inline, chevron at end). */
export function SettingsFoldSummary({ title, meta, className }: Props) {
  return (
    <div className={cn('org-fold-summary-inner flex min-w-0 flex-1 items-center gap-2', className)}>
      <span className="org-fold-summary-title shrink-0 text-sm font-semibold leading-snug text-foreground">
        {title}
      </span>
      {meta ? (
        <div className="org-fold-summary-meta flex min-w-0 flex-wrap items-center gap-1.5">{meta}</div>
      ) : null}
      <ChevronDown
        className="org-fold-chevron ml-auto size-4 shrink-0 text-muted-foreground transition-transform duration-200"
        aria-hidden
      />
    </div>
  )
}
