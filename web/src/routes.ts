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

export const DEFAULT_ROUTES = ['library', 'skills', 'org', 'stats', 'tasks', 'instance'] as const
export type DefaultRoute = (typeof DEFAULT_ROUTES)[number]

export function defaultRoutePath(route: DefaultRoute): string {
  switch (route) {
    case 'library':
      return LIBRARY_DEFAULT
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
  }
}

export function allowedDefaultRoutes(me: Me | null): DefaultRoute[] {
  const routes: DefaultRoute[] = ['tasks']
  if (me?.org) {
    routes.push('library', 'skills', 'org')
    if (me.user.role === 'org_admin') routes.push('stats')
  }
  if (Boolean(me?.user.is_instance_admin && !me?.impersonating)) routes.push('instance')
  return routes
}

export function resolveHomePath(me: Me | null): string {
  const allowed = allowedDefaultRoutes(me)
  const stored = me?.user.default_route as DefaultRoute | undefined
  if (stored && allowed.includes(stored)) return defaultRoutePath(stored)
  if (me?.org) return LIBRARY_DEFAULT
  if (Boolean(me?.user.is_instance_admin && !me?.impersonating)) return '/app/instance'
  return '/app/tasks'
}

export function isDefaultRoute(value: string | undefined): value is DefaultRoute {
  return DEFAULT_ROUTES.includes(value as DefaultRoute)
}
