import type { TFunction } from 'i18next'
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

export const DEFAULT_ROUTES = [
  'library/audio',
  'library/transcripts',
  'library/summaries',
  'skills',
  'org',
  'stats',
  'tasks',
  'instance',
] as const
export type DefaultRoute = (typeof DEFAULT_ROUTES)[number]

const LEGACY_DEFAULT_ROUTE = 'library'

export function normalizeDefaultRoute(value: string | undefined): DefaultRoute | undefined {
  if (value === LEGACY_DEFAULT_ROUTE) return 'library/audio'
  return isDefaultRoute(value) ? value : undefined
}

export function defaultRoutePath(route: DefaultRoute): string {
  if (route.startsWith('library/')) {
    const tab = route.slice('library/'.length)
    if (isLibraryTab(tab)) return libraryPath(tab)
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
      return '/app/instance'
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
  if (Boolean(me?.user.is_instance_admin && !me?.impersonating)) routes.push('instance')
  return routes
}

export function resolveLoginPath(me: Me | null): string {
  const org = me?.org
  if (org?.sso?.enabled && org.id) return `/sso/${org.id}`
  return '/login'
}

export function resolveHomePath(me: Me | null): string {
  const allowed = allowedDefaultRoutes(me)
  const stored = normalizeDefaultRoute(me?.user.default_route)
  if (stored && allowed.includes(stored)) return defaultRoutePath(stored)
  if (me?.org) return LIBRARY_DEFAULT
  if (Boolean(me?.user.is_instance_admin && !me?.impersonating)) return '/app/instance'
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
  return t(`nav.${route}`)
}
