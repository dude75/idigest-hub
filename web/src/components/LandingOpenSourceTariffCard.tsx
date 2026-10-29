import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { appLandingPricingBtn, appLandingPricingName, appLandingPricingQuotaMain, appMutedText, appPricingQuotaNote } from './app/appTypography'
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
        <h3 className={appLandingPricingName}>{t('landing.tariffOpenSourceName')}</h3>
        <p className={cn(appMutedText, 'landing-pricing-subtitle')}>{t('landing.tariffOpenSourceSubtitle')}</p>
      </div>
      <div className="landing-pricing-quota">
        <div className={appLandingPricingQuotaMain}>
          <span className="landing-pricing-icon" aria-hidden="true">
            ⚡
          </span>
          <span>{t('landing.tariffOpenSourceQuota')}</span>
        </div>
        <p className={appPricingQuotaNote}>{t('landing.tariffOpenSourceQuotaNote')}</p>
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
      <span className={cn(appLandingPricingBtn, 'landing-pricing-btn landing-pricing-btn-oss')}>
        {t('landing.tariffOpenSourceBtn')}
      </span>
    </a>
  )
}
