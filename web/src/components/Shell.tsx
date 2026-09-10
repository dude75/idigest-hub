import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isInstanceAdmin, isOrgAdmin, useAuth } from '../auth'
import { LIBRARY_DEFAULT } from '../routes'
import { showError, WalletLabel } from '../util'
import { AppBrand } from './AppBrand'
import { GitHubLink } from './GitHubLink'
import { LanguageSwitcher } from './LanguageSwitcher'

export function Shell() {
  const { t } = useTranslation()
  const { me, refresh, logout } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const libraryActive = loc.pathname.startsWith('/app/library')
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
    <div>
      {me?.impersonating && (
        <div className="banner">
          <span>{t('impersonate.banner', { email: me.user.email })}</span>
          <button type="button" onClick={() => void stopImpersonate()}>{t('impersonate.stop')}</button>
        </div>
      )}
      <header className="topbar">
        <AppBrand link />
        <nav className="nav">
          {member && (
            <NavLink to={LIBRARY_DEFAULT} className={() => (libraryActive ? 'active' : '')}>
              {t('nav.library')}
            </NavLink>
          )}
          {member && <NavLink to="/app/skills">{t('nav.skills')}</NavLink>}
          {member && <NavLink to="/app/org">{t('nav.org')}</NavLink>}
          {orgAdmin && <NavLink to="/app/stats">{t('nav.stats')}</NavLink>}
          <NavLink to="/app/tasks">{t('nav.tasks')}</NavLink>
          <NavLink to="/app/profile">{t('nav.profile')}</NavLink>
          {instance && <NavLink to="/app/instance">{t('nav.instance')}</NavLink>}
        </nav>
        <div className="right row">
          <WalletLabel unlimited={me?.org?.unlimited} balance={me?.org?.balance} />
          <GitHubLink />
          <LanguageSwitcher />
          <button
            type="button"
            onClick={() => {
              void logout()
            }}
          >
            {t('nav.logout')}
          </button>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </div>
  )
}
