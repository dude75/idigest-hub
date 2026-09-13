export type SecurityTab = 'audit'

export const SECURITY_TABS: SecurityTab[] = ['audit']

export function resolveSecurityTab(tabParam: string | null): SecurityTab {
  return SECURITY_TABS.includes(tabParam as SecurityTab) ? (tabParam as SecurityTab) : 'audit'
}
