import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { MfaSetupPanel } from '../components/MfaSetupPanel'
import { resolveAuthBlockPath, resolveAuthContinuationPath } from '../routes'

export function Enroll2faPage() {
  const { t } = useTranslation()
  const { ready, me, refresh, logout } = useAuth()
  const nav = useNavigate()

  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!me) return <Navigate to="/login" replace />

  const block = resolveAuthBlockPath(me)
  if (block === '/change-password') return <Navigate to="/change-password" replace />
  if (block === '/login') return <Navigate to="/login" replace />
  if (!me.mfa_enrollment_required && me.mfa_enabled) {
    return <Navigate to={resolveAuthContinuationPath(me)} replace />
  }
  if (!me.mfa_enrollment_required && !me.mfa_enabled) {
    return <Navigate to="/app/profile" replace />
  }

  return (
    <AuthPageShell>
      <div className="card auth-card stack">
        <h1>{t('mfa.enrollTitle')}</h1>
        <p className="muted">{t('mfa.enrollRequired')}</p>
        <MfaSetupPanel
          onComplete={async () => {
            const next = await refresh()
            nav(resolveAuthContinuationPath(next), { replace: true })
          }}
        />
        <button type="button" onClick={() => void logout()}>
          {t('nav.logout')}
        </button>
      </div>
    </AuthPageShell>
  )
}
