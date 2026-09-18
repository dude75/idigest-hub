import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ApiError, api } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { showError } from '../util'

/** Matches PASSWORD_RESET_COOLDOWN_SEC on the backend. */
const RESET_COOLDOWN_SEC = 900

function cooldownMinutes(sec: number): number {
  return Math.max(1, Math.ceil(sec / 60))
}

export function ForgotPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone } = useAuth()
  const [email, setEmail] = useState('')
  const [ok, setOk] = useState(false)
  const [busy, setBusy] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const id = window.setInterval(() => {
      setCooldown((value) => (value <= 1 ? 0 : value - 1))
    }, 1000)
    return () => window.clearInterval(id)
  }, [cooldown > 0])

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />

  const locked = busy || cooldown > 0

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (locked) return
    setBusy(true)
    try {
      await api('/auth/password/reset/request', { method: 'POST', body: JSON.stringify({ email }) })
      setOk(true)
      setCooldown(RESET_COOLDOWN_SEC)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'rate_limited' && err.retryAfter) {
        setCooldown(err.retryAfter)
      }
      showError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthPageShell>
      <form className="card auth-card stack" onSubmit={(e) => void onSubmit(e)}>
        <h1>{t('auth.forgot')}</h1>
        {ok && <p className="ok">{t('auth.sent')}</p>}
        {cooldown > 0 && (
          <p className="muted">{t('auth.resetCooldown', { minutes: cooldownMinutes(cooldown) })}</p>
        )}
        <label>
          {t('common.email')}
          <input
            type="email"
            required
            disabled={locked}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <button className="primary" disabled={locked} type="submit">{t('common.confirm')}</button>
        <Link to="/login">{t('auth.toLogin')}</Link>
      </form>
    </AuthPageShell>
  )
}
