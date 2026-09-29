import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth'
import { AuthCard } from '../components/auth/AuthCard'
import { AuthPageShell } from '../components/AuthPageShell'
import { MfaSetupPanel } from '../components/MfaSetupPanel'
import { resolveAuthBlockPath, resolveAuthContinuationPath } from '../routes'
import { Button } from '@/components/ui/button'

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
      <AuthCard className="max-w-lg" title={t('mfa.enrollTitle')} description={t('mfa.enrollRequired')}>
        <div className="space-y-4">
          <MfaSetupPanel
            onComplete={async () => {
              const next = await refresh()
              nav(resolveAuthContinuationPath(next), { replace: true })
            }}
          />
          <Button className="w-full" type="button" variant="outline" onClick={() => void logout()}>
            {t('nav.logout')}
          </Button>
        </div>
      </AuthCard>
    </AuthPageShell>
  )
}
