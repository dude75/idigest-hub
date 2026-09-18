import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

type Props = {
  to?: string
  title: ReactNode
  meta?: ReactNode
  /** Rendered below meta, outside the muted wrapper (e.g. task errors). */
  belowMeta?: ReactNode
  trailing?: ReactNode
  /** Title link fills the row; meta omitted (e.g. nested summary links). */
  compact?: boolean
}

export function ListRow({ to, title, meta, belowMeta, trailing, compact }: Props) {
  if (compact && to) {
    return (
      <div className="item row">
        <Link className="title grow" to={to}>{title}</Link>
        {trailing}
      </div>
    )
  }

  return (
    <div className="item row">
      <div className="grow">
        {to ? (
          <Link className="title" to={to}>{title}</Link>
        ) : (
          <span className="title">{title}</span>
        )}
        {meta && <div className="muted item-meta">{meta}</div>}
        {belowMeta}
      </div>
      {trailing}
    </div>
  )
}
