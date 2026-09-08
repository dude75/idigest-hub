import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isInstanceAdmin, isOrgAdmin, useAuth } from '../auth'
import { WalletLabel } from '../util'
import { LanguageSwitcher } from './LanguageSwitcher'

export function Shell() {
  const { t } = useTranslation()
  const { me, refresh, logout } = useAuth()
  const nav = useNavigate()
  const member = Boolean(me?.org)
  const orgAdmin = isOrgAdmin(me)
  const instance = isInstanceAdmin(me)

  async function stopImpersonate() {
    const back = me?.actor?.is_instance_admin ? '/app/instance' : '/app/org'
    await api('/impersonate', { method: 'DELETE' })
    await refresh()
    nav(back)
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
        <NavLink to="/app" className="brand">{t('app')}</NavLink>
        <nav className="nav">
          {member && <NavLink to="/app" end>{t('nav.library')}</NavLink>}
          {member && <NavLink to="/app/skills">{t('nav.skills')}</NavLink>}
          {member && <NavLink to="/app/org">{t('nav.org')}</NavLink>}
          {orgAdmin && <NavLink to="/app/stats">{t('nav.stats')}</NavLink>}
          <NavLink to="/app/tasks">{t('nav.tasks')}</NavLink>
          <NavLink to="/app/profile">{t('nav.profile')}</NavLink>
          {instance && <NavLink to="/app/instance">{t('nav.instance')}</NavLink>}
        </nav>
        <div className="right row">
          <WalletLabel unlimited={me?.org?.unlimited} balance={me?.org?.balance} />
          <LanguageSwitcher />
          <button
            type="button"
            onClick={() => {
              void logout().then(() => nav('/login'))
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
