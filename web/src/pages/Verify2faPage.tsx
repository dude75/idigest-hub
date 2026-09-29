import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthCard } from '../components/auth/AuthCard'
import { AuthField } from '../components/auth/AuthField'
import { AuthPageShell } from '../components/AuthPageShell'
import { clearMfaChallengeId, readMfaChallengeId } from '../mfa'
import { resolveAuthContinuationPath } from '../routes'
import { showError } from '../util'
import { AppSubmitButton } from '@/components/app/AdminUi'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function Verify2faPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone, me, refresh } = useAuth()
  const nav = useNavigate()
  const challengeId = readMfaChallengeId()
  const [code, setCode] = useState('')
  const [recovery, setRecovery] = useState('')
  const [useRecovery, setUseRecovery] = useState(false)
  const [busy, setBusy] = useState(false)

  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!bootstrapDone) return <Navigate to="/setup" replace />
  if (me) return <Navigate to={resolveAuthContinuationPath(me)} replace />
  if (!challengeId) return <Navigate to="/login" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!challengeId) return
    setBusy(true)
    try {
      if (useRecovery) {
        await api('/auth/mfa/recover', {
          method: 'POST',
          body: JSON.stringify({ challenge_id: challengeId, recovery_code: recovery.trim() }),
        })
      } else {
        await api('/auth/mfa/verify', {
          method: 'POST',
          body: JSON.stringify({ challenge_id: challengeId, code: code.trim() }),
        })
      }
      clearMfaChallengeId()
      const next = await refresh()
      nav(resolveAuthContinuationPath(next), { replace: true })
    } catch (err) {
      showError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthPageShell>
      <AuthCard
        title={t('mfa.verifyTitle')}
        description={useRecovery ? t('mfa.recoveryHint') : t('mfa.verifyHint')}
      >
        <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
          {!useRecovery ? (
            <AuthField label={t('mfa.code')} htmlFor="mfa-code">
              <Input
                id="mfa-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9 ]*"
                maxLength={8}
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </AuthField>
          ) : (
            <AuthField label={t('mfa.recoveryCode')} htmlFor="mfa-recovery">
              <Input
                id="mfa-recovery"
                type="text"
                autoComplete="off"
                spellCheck={false}
                required
                value={recovery}
                onChange={(e) => setRecovery(e.target.value)}
              />
            </AuthField>
          )}
          <AppSubmitButton
            className="w-full"
            type="submit"
            ready={useRecovery ? recovery.trim().length > 0 : code.replace(/\s/g, '').length >= 6}
            busy={busy}
          >
            {t('auth.login')}
          </AppSubmitButton>
          <Button className="w-full" type="button" variant="outline" onClick={() => setUseRecovery((v) => !v)}>
            {useRecovery ? t('mfa.useAuthenticator') : t('mfa.useRecovery')}
          </Button>
          <Link to="/login" className="text-sm" onClick={clearMfaChallengeId}>
            {t('common.back')}
          </Link>
        </form>
      </AuthCard>
    </AuthPageShell>
  )
}
