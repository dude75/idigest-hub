import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AppHoverHint } from '@/components/app/AppHoverHint'
import { appListRowMeta, appListRowTitle } from '@/components/app/appTypography'
import { cn } from '@/lib/utils'

type Props = {
  to?: string
  title: ReactNode
  /** HoverCard detail; defaults to string `title` when set. */
  hint?: ReactNode
  meta?: ReactNode
  /** Rendered below meta, outside the muted wrapper (e.g. task errors). */
  belowMeta?: ReactNode
  trailing?: ReactNode
  /** Title link fills the row; meta omitted (e.g. nested summary links). */
  compact?: boolean
}

function titleHoverContent(title: ReactNode, hint?: ReactNode): ReactNode | undefined {
  if (hint != null && hint !== '') return hint
  if (typeof title === 'string' && title.trim()) return title
  return undefined
}

function TitleNode({
  to,
  title,
  hint,
  className,
}: {
  to?: string
  title: ReactNode
  hint?: ReactNode
  className?: string
}) {
  const hover = titleHoverContent(title, hint)
  const titleClass = cn(appListRowTitle, className)
  const inner = to ? (
    <Link className={titleClass} to={to}>
      {title}
    </Link>
  ) : (
    <span className={titleClass}>{title}</span>
  )
  if (!hover) {
    return inner
  }
  return <AppHoverHint content={hover}>{inner}</AppHoverHint>
}

export function ListRow({ to, title, hint, meta, belowMeta, trailing, compact }: Props) {
  if (compact && to) {
    return (
      <div data-slot="list-row" className="item row">
        <TitleNode to={to} title={title} hint={hint} className="min-w-0 grow" />
        {trailing}
      </div>
    )
  }

  return (
    <div data-slot="list-row" className="item row gap-3">
      <div className="min-w-0 grow">
        <TitleNode to={to} title={title} hint={hint} />
        {meta ? <div className={appListRowMeta}>{meta}</div> : null}
        {belowMeta}
      </div>
      {trailing}
    </div>
  )
}
