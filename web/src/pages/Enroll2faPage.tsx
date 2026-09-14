import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth'
import { MfaSetupPanel } from '../components/MfaSetupPanel'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { resolveHomePath } from '../routes'

export function Enroll2faPage() {
  const { t } = useTranslation()
  const { ready, me, refresh, logout } = useAuth()
  const nav = useNavigate()

  if (ready && !me) return <Navigate to="/login" replace />
  if (ready && me && !me.mfa_enrollment_required && me.mfa_enabled) {
    return <Navigate to={resolveHomePath(me)} replace />
  }
  if (ready && me && !me.mfa_enrollment_required && !me.mfa_enabled) {
    return <Navigate to="/app/profile" replace />
  }

  return (
    <div className="auth-page">
      <div className="card auth-card stack">
        <div className="row">
          <h1 className="grow">{t('mfa.enrollTitle')}</h1>
          <LanguageSwitcher />
        </div>
        <p className="muted">{t('mfa.enrollRequired')}</p>
        <MfaSetupPanel
          onComplete={async () => {
            await refresh()
            nav('/app', { replace: true })
          }}
        />
        <button type="button" onClick={() => void logout()}>
          {t('nav.logout')}
        </button>
      </div>
    </div>
  )
}
