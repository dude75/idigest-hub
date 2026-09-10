import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AppBrand } from '../components/AppBrand'
import { GitHubLink } from '../components/GitHubLink'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { resolveHomePath } from '../routes'
import { arrangeTariffsForLanding } from '../landingTariffLayout'
import { LandingTariffGrid } from '../components/LandingTariffGrid'
import type { Tariff } from '../types'

const FEATURE_KEYS = ['transcription', 'summaries', 'library', 'orgs', 'billing', 'sso'] as const
const AUDIENCE_KEYS = ['it', 'managers', 'research', 'content'] as const
const FAQ_COUNT = 6

export function LandingPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone, me } = useAuth()
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const { ordered: sortedTariffs, popularTariffId } = useMemo(
    () => arrangeTariffsForLanding(tariffs),
    [tariffs],
  )

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
      <header className="landing-topbar topbar">
        <AppBrand />
        <nav className="landing-nav" aria-label="Landing">
          <a href="#how">{t('landing.navHow')}</a>
          <a href="#features">{t('landing.navFeatures')}</a>
          {tariffs.length > 0 && <a href="#pricing">{t('landing.navPricing')}</a>}
          <a href="#faq">{t('landing.navFaq')}</a>
        </nav>
        <div className="right row">
          <GitHubLink />
          <LanguageSwitcher />
          <Link to="/login" className="btn">{t('auth.login')}</Link>
          <Link to="/signup" className="btn primary">{t('auth.signup')}</Link>
        </div>
      </header>

      <section className="landing-hero">
        <div className="landing-hero-inner">
          <div className="landing-hero-copy">
            <p className="landing-eyebrow">{t('landing.eyebrow')}</p>
            <h1>{t('landing.headline')}</h1>
            <p className="landing-lead">{t('landing.lead')}</p>
            <div className="landing-cta">
              <Link to="/signup" className="btn primary landing-btn-lg">{t('auth.toSignup')}</Link>
              <Link to="/login" className="btn landing-btn-lg">{t('auth.login')}</Link>
            </div>
          </div>
          <div className="landing-preview" aria-hidden="true">
            <div className="landing-preview-chrome">
              <span />
              <span />
              <span />
            </div>
            <div className="landing-preview-tabs">
              <span className="active">{t('landing.previewTabAudio')}</span>
              <span>{t('landing.previewTabTranscript')}</span>
              <span>{t('landing.previewTabSummary')}</span>
            </div>
            <div className="landing-preview-wave">
              {Array.from({ length: 48 }, (_, i) => (
                <span key={i} style={{ height: `${18 + ((i * 7) % 28)}px` }} />
              ))}
            </div>
            <div className="landing-preview-transcript">
              <p><strong>00:01:12</strong> {t('landing.previewLine1')}</p>
              <p><strong>00:02:45</strong> {t('landing.previewLine2')}</p>
              <p className="landing-preview-summary">{t('landing.previewSummary')}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-trust">
        <p className="landing-trust-label">{t('landing.trustTitle')}</p>
        <ul className="landing-trust-list">
          {(['onPrem', 'sso', 'multiTenant', 'workers'] as const).map((key) => (
            <li key={key}>{t(`landing.trust.${key}`)}</li>
          ))}
        </ul>
      </section>

      <section className="landing-section" id="how">
        <div className="landing-section-head">
          <h2>{t('landing.howTitle')}</h2>
          <p className="muted">{t('landing.howLead')}</p>
        </div>
        <ol className="landing-steps-grid">
          {([1, 2, 3] as const).map((n) => (
            <li key={n} className="landing-step-card">
              <span className="landing-step-num">{n}</span>
              <h3>{t(`landing.step${n}Title`)}</h3>
              <p>{t(`landing.step${n}Desc`)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-section landing-section-alt" id="features">
        <div className="landing-section-head">
          <h2>{t('landing.featuresTitle')}</h2>
          <p className="muted">{t('landing.featuresLead')}</p>
        </div>
        <div className="landing-features-grid">
          {FEATURE_KEYS.map((key) => (
            <article key={key} className="landing-feature-card">
              <h3>{t(`landing.features.${key}.title`)}</h3>
              <p>{t(`landing.features.${key}.desc`)}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <div className="landing-section-head">
          <h2>{t('landing.audienceTitle')}</h2>
          <p className="muted">{t('landing.audienceLead')}</p>
        </div>
        <div className="landing-audience-grid">
          {AUDIENCE_KEYS.map((key) => (
            <article key={key} className="landing-audience-card">
              <h3>{t(`landing.audiences.${key}.title`)}</h3>
              <p>{t(`landing.audiences.${key}.desc`)}</p>
            </article>
          ))}
        </div>
      </section>

      {sortedTariffs.length > 0 && (
        <section className="landing-section landing-section-alt landing-pricing" id="pricing">
          <div className="landing-section-head landing-section-head-center">
            <h2>{t('landing.tariffsTitle')}</h2>
            <p className="muted">{t('landing.tariffsLead')}</p>
          </div>
          <LandingTariffGrid tariffs={sortedTariffs} popularTariffId={popularTariffId} />
        </section>
      )}

      <section className="landing-section" id="faq">
        <div className="landing-section-head landing-section-head-full">
          <h2>{t('landing.faqTitle')}</h2>
          <p className="muted">{t('landing.faqLead')}</p>
        </div>
        <div className="landing-faq">
          {Array.from({ length: FAQ_COUNT }, (_, i) => i + 1).map((n) => (
            <details key={n} className="landing-faq-item">
              <summary>{t(`landing.faq${n}q`)}</summary>
              <p>{t(`landing.faq${n}a`)}</p>
            </details>
          ))}
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-footer-copy">
          <AppBrand />
          <p className="muted">{t('landing.footer')}</p>
        </div>
        <GitHubLink variant="footer" />
      </footer>
    </div>
  )
}
