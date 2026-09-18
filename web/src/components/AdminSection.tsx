import type { ReactNode } from 'react'

export function AdminPage({ children }: { children: ReactNode }) {
  return <div className="admin-page">{children}</div>
}

type AdminFormCardProps = {
  title: string
  lead?: ReactNode
  className?: string
  children: ReactNode
}

export function AdminFormCard({ title, lead, className, children }: AdminFormCardProps) {
  return (
    <div className={['card stack admin-form-card', className].filter(Boolean).join(' ')}>
      <div className="stats-section-head">
        <h2>{title}</h2>
        {lead ? <p className="admin-lead">{lead}</p> : null}
      </div>
      {children}
    </div>
  )
}

type AdminTableCardProps = {
  title?: string
  lead?: ReactNode
  className?: string
  children: ReactNode
  empty?: string
  isEmpty?: boolean
}

export function AdminTableCard({ title, lead, className, children, empty, isEmpty }: AdminTableCardProps) {
  return (
    <div className={['card stack admin-table-card', className].filter(Boolean).join(' ')}>
      {title ? (
        <div className="stats-section-head">
          <h2>{title}</h2>
          {lead ? <p className="admin-lead">{lead}</p> : null}
        </div>
      ) : null}
      {isEmpty && empty ? <p className="stats-empty">{empty}</p> : children}
    </div>
  )
}
