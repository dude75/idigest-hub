import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { LIBRARY_DEFAULT } from '../routes'
import { ErrorBox } from '../util'

export function LoginPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone, me, refresh } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />
  if (ready && me) return <Navigate to={me.must_change_password ? '/change-password' : LIBRARY_DEFAULT} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      await refresh()
      nav(LIBRARY_DEFAULT, { replace: true })
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
          <h1 className="grow">{t('auth.login')}</h1>
          <LanguageSwitcher />
        </div>
        <ErrorBox err={err} />
        <label>
          {t('common.email')}
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          {t('common.password')}
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <button className="primary" disabled={busy} type="submit">{t('auth.login')}</button>
        <div className="stack">
          <Link to="/signup">{t('auth.toSignup')}</Link>
          <Link to="/forgot">{t('auth.toForgot')}</Link>
        </div>
      </form>
    </div>
  )
}
