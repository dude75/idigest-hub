import { cn } from '@/lib/utils'
import { userDisplayName, userHasDistinctDisplayName, type UserLabelSource } from '../userDisplay'

type Props = {
  user: UserLabelSource
  className?: string
}

/** Org member tables: email is primary; optional name on a second line (no hover underline). */
export function OrgMemberCell({ user, className }: Props) {
  const email = (user.email || '').trim()
  const hasName = userHasDistinctDisplayName(user)
  if (!hasName) {
    return <span className={cn('min-w-0 break-all', className)}>{email}</span>
  }
  return (
    <div className={cn('org-member-cell', className)}>
      <div className="org-member-cell-email min-w-0 break-all">{email}</div>
      <div className="org-member-cell-name min-w-0 break-all">{userDisplayName(user)}</div>
    </div>
  )
}
