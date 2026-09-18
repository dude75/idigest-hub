import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from './api'
import { setDateTimePrefs } from './util/datetimeFormat'
import { showError } from './util'
import { resolveLoginPath, type DefaultRoute } from './routes'
import type { Locale, Me } from './types'

type AuthState = {
  ready: boolean
  bootstrapDone: boolean
  bootstrapError: unknown
  me: Me | null
  refresh: () => Promise<Me | null>
  setLocale: (locale: Locale) => Promise<void>
  setDefaultRoute: (route: DefaultRoute) => Promise<void>
  setDateTimeFormat: (format: string | null) => Promise<void>
  setTimezone: (timezone: string | null) => Promise<void>
  setShowOnlyMyItems: (enabled: boolean) => Promise<void>
  logout: () => Promise<void>
}

const AuthCtx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { i18n } = useTranslation()
  const [ready, setReady] = useState(false)
  const [bootstrapDone, setBootstrapDone] = useState(false)
  const [bootstrapError, setBootstrapError] = useState<unknown>(null)
  const [me, setMe] = useState<Me | null>(null)

  const refresh = useCallback(async (): Promise<Me | null> => {
    setBootstrapError(null)
    const status = await api<{ bootstrap_done: boolean }>('/setup/status')
    setBootstrapDone(status.bootstrap_done)
    if (!status.bootstrap_done) {
      setMe(null)
      return null
    }
    try {
      const next = await api<Me>('/me')
      setMe(next)
      setDateTimePrefs(next.date_time_prefs)
      if (next.user.locale && next.user.locale !== i18n.language) {
        localStorage.setItem('locale', next.user.locale)
        await i18n.changeLanguage(next.user.locale)
      }
      return next
    } catch (err) {
      if (err instanceof ApiError && err.code === 'unauthorized') {
        setMe(null)
        return null
      }
      throw err
    }
  }, [i18n])

  useEffect(() => {
    refresh()
      .catch((err) => {
        setBootstrapError(err)
        showError(err)
        setMe(null)
      })
      .finally(() => setReady(true))
  }, [refresh])

  const setLocale = useCallback(
    async (locale: Locale) => {
      localStorage.setItem('locale', locale)
      await i18n.changeLanguage(locale)
      if (me) {
        const next = await api<Me>('/me', { method: 'PATCH', body: JSON.stringify({ locale }) })
        setMe(next)
        setDateTimePrefs(next.date_time_prefs)
      }
    },
    [i18n, me],
  )

  const setDefaultRoute = useCallback(
    async (route: DefaultRoute) => {
      if (me) {
        const next = await api<Me>('/me', { method: 'PATCH', body: JSON.stringify({ default_route: route }) })
        setMe(next)
        setDateTimePrefs(next.date_time_prefs)
      }
    },
    [me],
  )

  const setDateTimeFormat = useCallback(
    async (format: string | null) => {
      if (me) {
        const next = await api<Me>('/me', { method: 'PATCH', body: JSON.stringify({ date_time_format: format }) })
        setMe(next)
        setDateTimePrefs(next.date_time_prefs)
      }
    },
    [me],
  )

  const setTimezone = useCallback(
    async (timezone: string | null) => {
      if (me) {
        const next = await api<Me>('/me', { method: 'PATCH', body: JSON.stringify({ timezone }) })
        setMe(next)
        setDateTimePrefs(next.date_time_prefs)
      }
    },
    [me],
  )

  const setShowOnlyMyItems = useCallback(
    async (enabled: boolean) => {
      if (me) {
        const next = await api<Me>('/me', { method: 'PATCH', body: JSON.stringify({ show_only_my_items: enabled }) })
        setMe(next)
        setDateTimePrefs(next.date_time_prefs)
      }
    },
    [me],
  )

  const logout = useCallback(async () => {
    const redirect = resolveLoginPath(me)
    await api('/auth/logout', { method: 'POST' })
    window.location.replace(redirect)
  }, [me])

  const value = useMemo(
    () => ({
      ready,
      bootstrapDone,
      bootstrapError,
      me,
      refresh,
      setLocale,
      setDefaultRoute,
      setDateTimeFormat,
      setTimezone,
      setShowOnlyMyItems,
      logout,
    }),
    [ready, bootstrapDone, bootstrapError, me, refresh, setLocale, setDefaultRoute, setDateTimeFormat, setTimezone, setShowOnlyMyItems, logout],
  )

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('AuthProvider missing')
  return ctx
}

export function isOrgAdmin(me: Me | null): boolean {
  return me?.user.role === 'org_admin'
}

export function isInstanceAdmin(me: Me | null): boolean {
  return Boolean(me?.user.is_instance_admin && !me.impersonating)
}
