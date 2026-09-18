export type SecurityTab = 'audit' | 'encryption'

export const SECURITY_TABS: SecurityTab[] = ['audit', 'encryption']

export function resolveSecurityTab(tabParam: string | null): SecurityTab {
  return SECURITY_TABS.includes(tabParam as SecurityTab) ? (tabParam as SecurityTab) : 'audit'
}
