import { useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { ErrorBox } from '../util'

export function ForgotPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone } = useAuth()
  const [email, setEmail] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [ok, setOk] = useState(false)
  const [busy, setBusy] = useState(false)

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await api('/auth/password/reset/request', { method: 'POST', body: JSON.stringify({ email }) })
      setOk(true)
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
          <h1 className="grow">{t('auth.forgot')}</h1>
          <LanguageSwitcher />
        </div>
        <ErrorBox err={err} />
        {ok && <p className="ok">{t('auth.sent')}</p>}
        <label>
          {t('common.email')}
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <button className="primary" disabled={busy} type="submit">{t('common.confirm')}</button>
        <Link to="/login">{t('auth.toLogin')}</Link>
      </form>
    </div>
  )
}
