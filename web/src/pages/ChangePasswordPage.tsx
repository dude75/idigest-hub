import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { resolveAuthBlockPath, resolveAuthContinuationPath } from '../routes'
import { showError } from '../util'

export function ChangePasswordPage() {
  const { t } = useTranslation()
  const { ready, me, refresh, logout } = useAuth()
  const nav = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  const forced = Boolean(me?.must_change_password)

  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!me) return <Navigate to="/login" replace />

  const block = resolveAuthBlockPath(me)
  if (block === '/enroll-2fa') return <Navigate to="/enroll-2fa" replace />
  if (block === '/accept-agreement') return <Navigate to="/accept-agreement" replace />
  if (block === '/login') return <Navigate to="/login" replace />
  if (block !== '/change-password') {
    return <Navigate to={resolveAuthContinuationPath(me)} replace />
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      await api('/auth/password/change', {
        method: 'POST',
        body: JSON.stringify({
          current_password: forced ? undefined : current,
          new_password: next,
        }),
      })
      const profile = await refresh()
      nav(resolveAuthContinuationPath(profile), { replace: true })
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthPageShell>
      <form className="card auth-card stack" onSubmit={(e) => void onSubmit(e)}>
        <h1>{t('auth.changePassword')}</h1>
        {forced && <p className="admin-lead">{t('auth.mustChange')}</p>}
        {!forced && (
          <label>
            {t('auth.currentPassword')}
            <input type="password" required value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
          </label>
        )}
        <label>
          {t('auth.newPassword')}
          <input type="password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
        </label>
        <button className="primary" disabled={busy} type="submit">{t('common.save')}</button>
        <button
          type="button"
          onClick={() => {
            void logout()
          }}
        >
          {t('nav.logout')}
        </button>
      </form>
    </AuthPageShell>
  )
}
