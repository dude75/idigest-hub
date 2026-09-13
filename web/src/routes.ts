import type { TFunction } from 'i18next'
import { INSTANCE_TABS, type InstanceTab } from './pages/instance/constants'
import { SECURITY_TABS, type SecurityTab } from './pages/security/constants'
import type { Me } from './types'

export const LIBRARY_TABS = ['audio', 'transcripts', 'summaries'] as const
export type LibraryTab = (typeof LIBRARY_TABS)[number]

export function libraryPath(tab: LibraryTab = 'audio'): string {
  return `/app/library/${tab}`
}

export const LIBRARY_DEFAULT = libraryPath('audio')

export function isLibraryTab(value: string | undefined): value is LibraryTab {
  return LIBRARY_TABS.includes(value as LibraryTab)
}

export function instancePath(tab: InstanceTab = 'stats'): string {
  return tab === 'stats' ? '/app/instance' : `/app/instance?tab=${tab}`
}

export function isInstanceTab(value: string | undefined): value is InstanceTab {
  return INSTANCE_TABS.includes(value as InstanceTab)
}

export function securityPath(tab: SecurityTab = 'audit'): string {
  return tab === 'audit' ? '/app/security' : `/app/security?tab=${tab}`
}

export function isSecurityTab(value: string | undefined): value is SecurityTab {
  return SECURITY_TABS.includes(value as SecurityTab)
}

export const DEFAULT_ROUTES = [
  'library/audio',
  'library/transcripts',
  'library/summaries',
  'skills',
  'org',
  'stats',
  'tasks',
  'instance/stats',
  'instance/workers',
  'instance/tariffs',
  'instance/orgs',
  'instance/settings',
  'instance/baseSkills',
  'instance',
  'security/audit',
  'security/encryption',
] as const
export type DefaultRoute = (typeof DEFAULT_ROUTES)[number]

const LEGACY_DEFAULT_ROUTE = 'library'
const LEGACY_INSTANCE_ROUTE = 'instance'

export function normalizeDefaultRoute(value: string | undefined): DefaultRoute | undefined {
  if (value === LEGACY_DEFAULT_ROUTE) return 'library/audio'
  if (value === LEGACY_INSTANCE_ROUTE) return 'instance/stats'
  return isDefaultRoute(value) ? value : undefined
}

export function defaultRoutePath(route: DefaultRoute): string {
  if (route.startsWith('library/')) {
    const tab = route.slice('library/'.length)
    if (isLibraryTab(tab)) return libraryPath(tab)
  }
  if (route.startsWith('instance/')) {
    const tab = route.slice('instance/'.length)
    if (isInstanceTab(tab)) return instancePath(tab)
  }
  if (route.startsWith('security/')) {
    const tab = route.slice('security/'.length)
    if (isSecurityTab(tab)) return securityPath(tab)
  }
  switch (route) {
    case 'skills':
      return '/app/skills'
    case 'org':
      return '/app/org'
    case 'stats':
      return '/app/stats'
    case 'tasks':
      return '/app/tasks'
    case 'instance':
      return instancePath('stats')
    default:
      return LIBRARY_DEFAULT
  }
}

export function allowedDefaultRoutes(me: Me | null): DefaultRoute[] {
  const routes: DefaultRoute[] = ['tasks']
  if (me?.org) {
    routes.push('library/audio', 'library/transcripts', 'library/summaries', 'skills', 'org')
    if (me.user.role === 'org_admin') routes.push('stats')
  }
  if (Boolean(me?.user.is_instance_admin && !me?.impersonating)) {
    for (const tab of INSTANCE_TABS) routes.push(`instance/${tab}`)
    for (const tab of SECURITY_TABS) routes.push(`security/${tab}`)
  }
  return routes
}

export function resolveLoginPath(me: Me | null): string {
  const org = me?.org
  if (org?.id && (org.sso?.enabled || me?.user.auth_provider === 'oidc')) {
    return `/sso/${org.id}`
  }
  return '/login'
}

export function resolveHomePath(me: Me | null): string {
  const allowed = allowedDefaultRoutes(me)
  const stored = normalizeDefaultRoute(me?.user.default_route)
  if (stored && allowed.includes(stored)) return defaultRoutePath(stored)
  if (me?.org) return LIBRARY_DEFAULT
  if (Boolean(me?.user.is_instance_admin && !me?.impersonating)) return instancePath('stats')
  return '/app/tasks'
}

export function isDefaultRoute(value: string | undefined): value is DefaultRoute {
  return DEFAULT_ROUTES.includes(value as DefaultRoute)
}

export function defaultRouteLabel(route: DefaultRoute, t: TFunction): string {
  if (route.startsWith('library/')) {
    const tab = route.slice('library/'.length)
    if (isLibraryTab(tab)) return `${t('nav.library')} · ${t(`library.${tab}`)}`
  }
  if (route.startsWith('instance/')) {
    const tab = route.slice('instance/'.length)
    if (isInstanceTab(tab)) return `${t('nav.instance')} · ${t(`instance.${tab}`)}`
  }
  if (route.startsWith('security/')) {
    const tab = route.slice('security/'.length)
    if (isSecurityTab(tab)) return `${t('nav.security')} · ${t(`security.${tab}`)}`
  }
  return t(`nav.${route}`)
}
