import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { isInstanceAdmin, useAuth } from '../auth'
import { LanguageSwitcher } from '../components/LanguageSwitcher'

export function LandingPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone, me } = useAuth()

  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!bootstrapDone) return <Navigate to="/setup" replace />
  if (me?.must_change_password) return <Navigate to="/change-password" replace />
  if (me && !me.org && isInstanceAdmin(me)) return <Navigate to="/app/instance" replace />
  if (me) return <Navigate to="/app" replace />

  return (
    <div className="landing">
      <header className="topbar">
        <span className="brand">{t('app')}</span>
        <div className="right row">
          <LanguageSwitcher />
          <Link to="/login" className="btn">{t('auth.login')}</Link>
          <Link to="/signup" className="btn primary">{t('auth.signup')}</Link>
        </div>
      </header>
      <main className="landing-main">
        <h1>{t('landing.headline')}</h1>
        <p className="landing-lead">{t('landing.lead')}</p>
        <ol className="landing-steps">
          <li>{t('landing.step1')}</li>
          <li>{t('landing.step2')}</li>
          <li>{t('landing.step3')}</li>
        </ol>
        <div className="landing-cta">
          <Link to="/signup" className="btn primary">{t('auth.toSignup')}</Link>
          <Link to="/login" className="btn">{t('auth.login')}</Link>
        </div>
      </main>
    </div>
  )
}
