import { useState, type FormEvent } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { ErrorBox } from '../util'

export function ResetPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone } = useAuth()
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [password, setPassword] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const [ok, setOk] = useState(false)
  const [busy, setBusy] = useState(false)

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await api('/auth/password/reset/confirm', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: password }),
      })
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
          <h1 className="grow">{t('auth.reset')}</h1>
          <LanguageSwitcher />
        </div>
        <ErrorBox err={err} />
        {ok ? (
          <>
            <p className="ok">{t('auth.resetDone')}</p>
            <Link to="/login">{t('auth.login')}</Link>
          </>
        ) : (
          <>
            <label>
              {t('auth.newPassword')}
              <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <button className="primary" disabled={busy || !token} type="submit">{t('common.save')}</button>
          </>
        )}
      </form>
    </div>
  )
}
