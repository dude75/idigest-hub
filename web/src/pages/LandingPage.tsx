import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AppBrand } from '../components/AppBrand'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { resolveHomePath } from '../routes'
import type { Tariff } from '../types'
import { formatBytes } from '../util'

export function LandingPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone, me } = useAuth()
  const [tariffs, setTariffs] = useState<Tariff[]>([])

  useEffect(() => {
    api<{ items: Tariff[] }>('/auth/signup-tariffs')
      .then((r) => setTariffs(r.items))
      .catch(() => setTariffs([]))
  }, [])

  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!bootstrapDone) return <Navigate to="/setup" replace />
  if (me?.must_change_password) return <Navigate to="/change-password" replace />
  if (me) return <Navigate to={resolveHomePath(me)} replace />

  return (
    <div className="landing">
      <header className="topbar">
        <AppBrand />
        <div className="right row">
          <LanguageSwitcher />
          <Link to="/login" className="btn">{t('auth.login')}</Link>
          <Link to="/signup" className="btn primary">{t('auth.signup')}</Link>
        </div>
      </header>
      <main className="landing-main">
        <h1>{t('landing.headline')}</h1>
        <p className="landing-lead">{t('landing.lead')}</p>
        <ol className="landing-steps">
          <li>{t('landing.step1')}</li>
          <li>{t('landing.step2')}</li>
          <li>{t('landing.step3')}</li>
        </ol>
        <div className="landing-cta">
          <Link to="/signup" className="btn primary">{t('auth.toSignup')}</Link>
          <Link to="/login" className="btn">{t('auth.login')}</Link>
        </div>
        {tariffs.length > 0 && (
          <section className="landing-tariffs">
            <h2>{t('landing.tariffsTitle')}</h2>
            <p className="muted">{t('landing.tariffsLead')}</p>
            <div className="tariff-grid">
              {tariffs.map((tr) => (
                <Link key={tr.id} className="tariff-card" to={`/signup?tariff=${encodeURIComponent(tr.id)}`}>
                  <div className="row">
                    <strong className="grow">{tr.name}</strong>
                    {tr.unlimited && <span className="badge">{t('instance.unlimited')}</span>}
                  </div>
                  <ul className="tariff-points">
                    <li>{t('landing.priceAudio', { price: tr.price_per_audio_sec })}</li>
                    <li>{t('landing.priceJob', { price: tr.price_per_summarize_job })}</li>
                    <li>{t('landing.priceChars', { price: tr.price_per_1k_summary_chars })}</li>
                    <li>
                      {tr.audio_retention_days > 0
                        ? t('landing.retention', { days: tr.audio_retention_days })
                        : t('landing.retentionForever')}
                    </li>
                    <li>{tr.api_enabled ? t('landing.apiYes') : t('landing.apiNo')}</li>
                    {!tr.unlimited && Number(tr.signup_credit) > 0 && (
                      <li>{t('landing.credit', { amount: tr.signup_credit })}</li>
                    )}
                    <li>{t('landing.uploadCap', { size: formatBytes(tr.max_upload_bytes) })}</li>
                  </ul>
                  <span className="tariff-cta">{t('landing.choose')}</span>
                </Link>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}
