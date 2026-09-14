import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { resolveHomePath } from '../routes'
import { showError } from '../util'

const CHALLENGE_KEY = 'mfa_challenge_id'

export function readMfaChallengeId(): string | null {
  try {
    return sessionStorage.getItem(CHALLENGE_KEY)
  } catch {
    return null
  }
}

export function clearMfaChallengeId(): void {
  try {
    sessionStorage.removeItem(CHALLENGE_KEY)
  } catch {
    /* ignore */
  }
}

export function storeMfaChallengeId(id: string): void {
  try {
    sessionStorage.setItem(CHALLENGE_KEY, id)
  } catch {
    /* ignore */
  }
}

export function Verify2faPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone, me, refresh } = useAuth()
  const nav = useNavigate()
  const challengeId = readMfaChallengeId()
  const [code, setCode] = useState('')
  const [recovery, setRecovery] = useState('')
  const [useRecovery, setUseRecovery] = useState(false)
  const [busy, setBusy] = useState(false)

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />
  if (ready && me) return <Navigate to={resolveHomePath(me)} replace />
  if (ready && !challengeId) return <Navigate to="/login" replace />

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
      await refresh()
      nav('/app', { replace: true })
    } catch (err) {
      showError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthPageShell>
      <form className="card auth-card stack" onSubmit={(e) => void onSubmit(e)}>
        <h1>{t('mfa.verifyTitle')}</h1>
        <p className="muted">{useRecovery ? t('mfa.recoveryHint') : t('mfa.verifyHint')}</p>
        {!useRecovery ? (
          <label>
            {t('mfa.code')}
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9 ]*"
              maxLength={8}
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </label>
        ) : (
          <label>
            {t('mfa.recoveryCode')}
            <input
              type="text"
              autoComplete="off"
              spellCheck={false}
              required
              value={recovery}
              onChange={(e) => setRecovery(e.target.value)}
            />
          </label>
        )}
        <button className="primary" disabled={busy} type="submit">
          {t('auth.login')}
        </button>
        <button type="button" onClick={() => setUseRecovery((v) => !v)}>
          {useRecovery ? t('mfa.useAuthenticator') : t('mfa.useRecovery')}
        </button>
        <Link to="/login" onClick={clearMfaChallengeId}>
          {t('common.back')}
        </Link>
      </form>
    </AuthPageShell>
  )
}
