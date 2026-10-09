import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isInstanceAdmin, isOrgAdmin, useAuth } from '../auth'
import { LIBRARY_DEFAULT } from '../routes'
import { showError, WalletLabel } from '../util'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { AppBrand } from './AppBrand'
import { GlobalMicRecordAccess } from './GlobalMicRecordAccess'
import { GitHubLink } from './GitHubLink'
import { LanguageSwitcher } from './LanguageSwitcher'

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
          <span>{t('impersonate.banner', { email: me.user.email })}</span>
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
            <NavLink to={LIBRARY_DEFAULT} className={() => (libraryActive ? 'active' : undefined)} end>
              {t('nav.library')}
            </NavLink>
          )}
          {member && (
            <NavLink to="/app/org" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              {t('nav.org')}
            </NavLink>
          )}
          {member && (
            <NavLink to="/app/public-links" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              {t('nav.publicLinks')}
            </NavLink>
          )}
          {orgAdmin && (
            <NavLink to="/app/stats" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              {t('nav.stats')}
            </NavLink>
          )}
          <NavLink to="/app/tasks" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            {t('nav.tasks')}
          </NavLink>
          {instance && (
            <NavLink to="/app/instance" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              {t('nav.instance')}
            </NavLink>
          )}
          {instance && (
            <NavLink to="/app/security" className={() => (securityActive ? 'active' : undefined)}>
              {t('nav.security')}
            </NavLink>
          )}
          <NavLink to="/app/profile" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            {t('nav.profile')}
          </NavLink>
        </nav>
        <div className="right row">
          <WalletLabel unlimited={me?.org?.unlimited} balance={me?.org?.balance} />
          <GitHubLink />
          <LanguageSwitcher />
          <Button type="button" size="sm" variant="outline" onClick={() => void logout()}>
            {t('nav.logout')}
          </Button>
        </div>
      </header>
      <GlobalMicRecordAccess />
      <main className="page">
        <Outlet />
      </main>
    </div>
  )
}
