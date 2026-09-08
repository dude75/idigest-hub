import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { LOCALES } from '../i18n'
import type { Locale } from '../types'
import { ErrorBox } from '../util'

export function SetupPage() {
  const { t, i18n } = useTranslation()
  const { ready, bootstrapDone, refresh } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (ready && bootstrapDone) return <Navigate to="/login" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await api('/setup', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          bootstrap_token: token,
          locale: i18n.language,
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
          <h1 className="grow">{t('auth.setup')}</h1>
          <LanguageSwitcher />
        </div>
        <ErrorBox err={err} />
        <label>
          {t('common.email')}
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          {t('common.password')}
          <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <label>
          {t('auth.bootstrapToken')}
          <input required value={token} onChange={(e) => setToken(e.target.value)} />
        </label>
        <label>
          Locale
          <select value={i18n.language} onChange={(e) => void i18n.changeLanguage(e.target.value as Locale)}>
            {LOCALES.map((l) => (
              <option key={l} value={l}>{t(`lang.${l}`)}</option>
            ))}
          </select>
        </label>
        <button className="primary" disabled={busy} type="submit">{t('common.save')}</button>
      </form>
    </div>
  )
}
