import { useTranslation } from 'react-i18next'
import { GITHUB_REPO_URL } from './GitHubLink'

const FEATURE_KEYS = [
  'landing.tariffFeatureApi',
  'landing.tariffOpenSourceFeatureFullSet',
  'landing.tariffOpenSourceFeatureSelfHosted',
  'landing.tariffFeatureSummaries',
] as const

export function LandingOpenSourceTariffCard() {
  const { t } = useTranslation()

  return (
    <a
      href={GITHUB_REPO_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="landing-pricing-card landing-pricing-card-oss"
    >
      <div className="landing-pricing-head">
        <h3>{t('landing.tariffOpenSourceName')}</h3>
        <p className="landing-pricing-subtitle">{t('landing.tariffOpenSourceSubtitle')}</p>
      </div>
      <div className="landing-pricing-quota">
        <div className="landing-pricing-quota-main">
          <span className="landing-pricing-icon" aria-hidden="true">
            ⚡
          </span>
          <span>{t('landing.tariffOpenSourceQuota')}</span>
        </div>
        <p className="landing-pricing-quota-note">{t('landing.tariffOpenSourceQuotaNote')}</p>
      </div>
      <ul className="landing-pricing-features">
        {FEATURE_KEYS.map((key) => (
          <li key={key}>
            <span className="landing-pricing-check" aria-hidden="true">
              ✓
            </span>
            {t(key)}
          </li>
        ))}
      </ul>
      <span className="landing-pricing-btn landing-pricing-btn-oss">{t('landing.tariffOpenSourceBtn')}</span>
    </a>
  )
}
