import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import type { Tariff } from '../types'
import { ErrorBox } from '../util'

export function SignupPage() {
  const { t, i18n } = useTranslation()
  const { ready, bootstrapDone, me, refresh } = useAuth()
  const nav = useNavigate()
  const [search] = useSearchParams()
  const wanted = search.get('tariff') || ''
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [tariffId, setTariffId] = useState('')
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<{ items: Tariff[] }>('/auth/signup-tariffs')
      .then((r) => {
        setTariffs(r.items)
        const match = r.items.find((item) => item.id === wanted)
        setTariffId((match || r.items[0])?.id || '')
      })
      .catch(setErr)
  }, [wanted])

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />
  if (ready && me) return <Navigate to="/app" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await api('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ email, password, tariff_id: tariffId, locale: i18n.language }),
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
          <h1 className="grow">{t('auth.signup')}</h1>
          <LanguageSwitcher />
        </div>
        <ErrorBox err={err} />
        {tariffs.length === 0 ? (
          <p className="muted">{t('auth.noSignup')}</p>
        ) : (
          <>
            <label>
              {t('common.email')}
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              {t('common.password')}
              <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <label>
              {t('auth.tariff')}
              <select value={tariffId} onChange={(e) => setTariffId(e.target.value)}>
                {tariffs.map((tr) => (
                  <option key={tr.id} value={tr.id}>
                    {tr.name}{tr.unlimited ? ` (${t('wallet.unlimited')})` : ''}
                  </option>
                ))}
              </select>
            </label>
            <button className="primary" disabled={busy} type="submit">{t('auth.signup')}</button>
          </>
        )}
        <Link to="/login">{t('auth.toLogin')}</Link>
      </form>
    </div>
  )
}
