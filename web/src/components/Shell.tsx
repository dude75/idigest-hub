import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isInstanceAdmin, isOrgAdmin, useAuth } from '../auth'
import { LIBRARY_DEFAULT } from '../routes'
import { showError, WalletLabel } from '../util'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { appChromeNavLink } from '@/components/app/appTypography'
import { AppBrand } from './AppBrand'
import { GlobalMicRecordAccess } from './GlobalMicRecordAccess'
import { MeTelegramProvider } from '../context/meTelegram'
import { GitHubLink } from './GitHubLink'
import { LanguageSwitcher } from './LanguageSwitcher'
import { userDisplayName } from '../userDisplay'

export function Shell() {
  const { t } = useTranslation()
  const { me, refresh, logout } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const libraryActive = loc.pathname.startsWith('/app/library')
  const securityActive = loc.pathname.startsWith('/app/security') || loc.pathname.startsWith('/app/audit')
  const member = Boolean(me?.org)
  const orgAdmin = isOrgAdmin(me)
  const instance = isInstanceAdmin(me)

  async function stopImpersonate() {
    const back = me?.actor?.is_instance_admin ? '/app/instance' : '/app/org'
    try {
      await api('/impersonate', { method: 'DELETE' })
      await refresh()
      nav(back)
    } catch (e) {
      showError(e)
    }
  }

  return (
    <div className="app-shell">
      {me?.impersonating && (
        <div className="banner">
          <span>{t('impersonate.banner', { email: userDisplayName(me.user) })}</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className={cn(
              'border-white/70 bg-white/15 text-white shadow-none',
              'hover:border-white/90 hover:bg-white/25 hover:text-white',
            )}
            onClick={() => void stopImpersonate()}
          >
            {t('impersonate.stop')}
          </Button>
        </div>
      )}
      <header className="topbar">
        <AppBrand />
        <nav className="nav">
          {member && (
            <NavLink
              to="/app/ingest"
              className={({ isActive }) => cn(appChromeNavLink, isActive && 'active')}
            >
              {t('nav.ingest')}
            </NavLink>
          )}
          {member && (
            <NavLink
              to={LIBRARY_DEFAULT}
              className={() => cn(appChromeNavLink, libraryActive && 'active')}
              end
            >
              {t('nav.library')}
            </NavLink>
          )}
          {member && (
            <NavLink
              to="/app/org"
              className={({ isActive }) => cn(appChromeNavLink, isActive && 'active')}
            >
              {t('nav.org')}
            </NavLink>
          )}
          {orgAdmin && (
            <NavLink
              to="/app/stats"
              className={({ isActive }) => cn(appChromeNavLink, isActive && 'active')}
            >
              {t('nav.stats')}
            </NavLink>
          )}
          <NavLink
            to="/app/tasks"
            className={({ isActive }) => cn(appChromeNavLink, isActive && 'active')}
          >
            {t('nav.tasks')}
          </NavLink>
          {instance && (
            <NavLink
              to="/app/instance"
              className={({ isActive }) => cn(appChromeNavLink, isActive && 'active')}
            >
              {t('nav.instance')}
            </NavLink>
          )}
          {instance && (
            <NavLink
              to="/app/security"
              className={() => cn(appChromeNavLink, securityActive && 'active')}
            >
              {t('nav.security')}
            </NavLink>
          )}
          <NavLink
            to="/app/profile"
            className={({ isActive }) => cn(appChromeNavLink, isActive && 'active')}
          >
            {t('nav.profile')}
          </NavLink>
        </nav>
        <div className="right flex flex-wrap items-center gap-2">
          <WalletLabel unlimited={me?.org?.unlimited} balance={me?.org?.balance} />
          <GitHubLink />
          <LanguageSwitcher />
          <Button type="button" size="sm" variant="outline" onClick={() => void logout()}>
            {t('nav.logout')}
          </Button>
        </div>
      </header>
      <MeTelegramProvider>
        <GlobalMicRecordAccess />
        <main className="page">
          <Outlet />
        </main>
      </MeTelegramProvider>
    </div>
  )
}
