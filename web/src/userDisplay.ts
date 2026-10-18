/** Display label for a user (name if set, otherwise email). */

export type UserLabelSource = {
  display_name?: string | null
  email?: string | null
}

export function userDisplayName(user: UserLabelSource | null | undefined): string {
  if (!user) return ''
  const name = (user.display_name || '').trim()
  if (name) return name
  return (user.email || '').trim()
}

/** Two letters for avatar fallback. */
export function userInitials(user: UserLabelSource | null | undefined): string {
  if (!user) return '?'
  const name = (user.display_name || '').trim()
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) {
    return `${parts[0]![0] ?? ''}${parts[1]![0] ?? ''}`.toUpperCase()
  }
  const single = parts[0] || (user.email || '').trim()
  if (single.length >= 2) return single.slice(0, 2).toUpperCase()
  return (single[0] ?? '?').toUpperCase()
}

export function userHasDistinctDisplayName(user: UserLabelSource | null | undefined): boolean {
  if (!user?.email) return false
  const name = (user.display_name || '').trim()
  return Boolean(name && name !== user.email.trim())
}

/** Dropdowns / filters: «Иван Иванов (user@example.com)» or email only. */
export function userPickerLabel(user: UserLabelSource | null | undefined): string {
  if (!user) return ''
  const email = (user.email || '').trim()
  if (userHasDistinctDisplayName(user)) {
    return `${userDisplayName(user)} (${email})`
  }
  return email || userDisplayName(user)
}

export function compareUsersByDisplayName(
  a: UserLabelSource & { id?: string },
  b: UserLabelSource & { id?: string },
): number {
  const left = userDisplayName(a).localeCompare(userDisplayName(b), undefined, { sensitivity: 'base' })
  if (left !== 0) return left
  return (a.email || '').localeCompare(b.email || '', undefined, { sensitivity: 'base' })
}

export function ownerListLabel(item: {
  owner_display_name?: string | null
  owner_email?: string | null
}): string {
  const name = (item.owner_display_name || '').trim()
  if (name) return name
  return (item.owner_email || '').trim()
}

export function memberMatchesQuery(
  user: UserLabelSource & { first_name?: string | null; last_name?: string | null },
  query: string,
): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const hay = [
    user.display_name,
    user.email,
    user.first_name,
    user.last_name,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return hay.includes(q)
}
