/** Human-readable skill catalog / scope for badges and filters. */
export function skillScopeLabel(
  scope: string,
  catalog: string | null | undefined,
  t: (key: string) => string,
): string {
  if (catalog === 'shared' || scope === 'shared') return t('skills.shared')
  if (scope === 'base') return t('skills.base')
  if (scope === 'org') return t('skills.org')
  if (scope === 'self') return t('skills.self')
  return catalog || scope
}
