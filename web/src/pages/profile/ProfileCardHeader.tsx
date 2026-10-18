import type { ReactNode } from 'react'
import { CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/** Profile tab card title + lead: same row when space allows, lead wraps on its own when narrow. */
export function ProfileCardHeader({
  title,
  lead,
  className,
}: {
  title: ReactNode
  lead?: ReactNode
  className?: string
}) {
  return (
    <CardHeader className={cn('profile-card-header', className)}>
      <div className="profile-card-header-row">
        <CardTitle className="profile-card-header-title shrink-0">{title}</CardTitle>
        {lead != null ? (
          <p data-slot="card-description" className="profile-card-lead admin-lead">
            {lead}
          </p>
        ) : null}
      </div>
    </CardHeader>
  )
}
