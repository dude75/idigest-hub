import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { ErrorBox } from '../util'

export function ChangePasswordPage() {
  const { t } = useTranslation()
  const { ready, me, refresh, logout } = useAuth()
  const nav = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const forced = Boolean(me?.must_change_password)

  if (ready && !me) return <Navigate to="/login" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await api('/auth/password/change', {
        method: 'POST',
        body: JSON.stringify({
          current_password: forced ? undefined : current,
          new_password: next,
        }),
      })
      await refresh()
      nav('/app', { replace: true })
    } catch (e) {
      setErr(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="card auth-card stack" onSubmit={(e) => void onSubmit(e)}>
        <div className="row">
          <h1 className="grow">{t('auth.changePassword')}</h1>
          <LanguageSwitcher />
        </div>
        {forced && <p className="muted">{t('auth.mustChange')}</p>}
        <ErrorBox err={err} />
        {!forced && (
          <label>
            {t('auth.currentPassword')}
            <input type="password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          </label>
        )}
        <label>
          {t('auth.newPassword')}
          <input type="password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
        </label>
        <button className="primary" disabled={busy} type="submit">{t('common.save')}</button>
        <button
          type="button"
          onClick={() => {
            void logout().then(() => nav('/login'))
          }}
        >
          {t('nav.logout')}
        </button>
      </form>
    </div>
  )
}
