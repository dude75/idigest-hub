import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { landingTariffSubtitleKey } from '../landingTariffLayout'
import type { Tariff } from '../types'
import { formatBytes, formatDecimal, formatRate } from '../util'

export { landingTariffSubtitleKey }

type Props = {
  tariff: Tariff
  popular?: boolean
  subtitleKey: 'regular' | 'standard' | 'expert'
  to: string
}

function estimateAudioMinutes(tariff: Tariff): number | null {
  const credit = Number(tariff.signup_credit)
  const pricePerSec = Number(tariff.price_per_audio_sec)
  if (credit <= 0 || pricePerSec <= 0) return null
  return Math.floor(credit / pricePerSec / 60)
}

export function LandingTariffCard({ tariff, popular, subtitleKey, to }: Props) {
  const { t } = useTranslation()
  const minutes = estimateAudioMinutes(tariff)
  const credit = Number(tariff.signup_credit)
  const pricePerSec = Number(tariff.price_per_audio_sec)
  const hasOverage = pricePerSec > 0

  const features: string[] = []
  if (tariff.api_enabled) features.push(t('landing.tariffFeatureApi'))
  features.push(t('landing.tariffFeatureUpload', { size: formatBytes(tariff.max_upload_bytes) }))
  features.push(
    tariff.audio_retention_days > 0
      ? t('landing.retention', { days: tariff.audio_retention_days })
      : t('landing.retentionForever'),
  )
  if (Number(tariff.price_per_1k_summary_chars) > 0) {
    features.push(t('landing.tariffFeatureSummaries'))
  }
  if (tariff.unlimited) features.push(t('landing.tariffFeatureUnlimited'))

  return (
    <Link
      to={to}
      className={`landing-pricing-card${popular ? ' landing-pricing-card-popular' : ''}`}
    >
      {popular && <span className="landing-pricing-popular">{t('landing.tariffPopular')}</span>}
      <div className="landing-pricing-head">
        <h3>{tariff.name}</h3>
        <p className="landing-pricing-subtitle">{t(`landing.tariffSubtitle.${subtitleKey}`)}</p>
      </div>
      <div className="landing-pricing-quota">
        {tariff.unlimited ? (
          <>
            <div className="landing-pricing-quota-main">
              <span className="landing-pricing-icon" aria-hidden="true">⚡</span>
              <span>{t('instance.unlimited')}</span>
            </div>
            <p className="landing-pricing-quota-note">{t('landing.tariffUnlimitedNote')}</p>
          </>
        ) : minutes !== null && minutes > 0 ? (
          <>
            <div className="landing-pricing-quota-main">
              <span className="landing-pricing-icon" aria-hidden="true">⚡</span>
              <span>{t('landing.tariffQuotaMinutes', { minutes })}</span>
            </div>
            {hasOverage && (
              <p className="landing-pricing-quota-note">
                {t('landing.tariffOverageAudio', { price: formatRate(tariff.price_per_audio_sec) })}
              </p>
            )}
          </>
        ) : credit > 0 ? (
          <>
            <div className="landing-pricing-quota-main">
              <span className="landing-pricing-icon" aria-hidden="true">⚡</span>
              <span>{t('landing.tariffQuotaCredit', { amount: formatDecimal(tariff.signup_credit) })}</span>
            </div>
            {hasOverage && (
              <p className="landing-pricing-quota-note">
                {t('landing.tariffOverageAudio', { price: formatRate(tariff.price_per_audio_sec) })}
              </p>
            )}
          </>
        ) : (
          <>
            <div className="landing-pricing-quota-main landing-pricing-quota-paygo">
              <span>{t('landing.tariffPayAsYouGo')}</span>
            </div>
            {hasOverage && (
              <p className="landing-pricing-quota-note">
                {t('landing.priceAudio', { price: formatRate(tariff.price_per_audio_sec) })}
              </p>
            )}
          </>
        )}
      </div>
      <ul className="landing-pricing-features">
        {features.map((item) => (
          <li key={item}>
            <span className="landing-pricing-check" aria-hidden="true">✓</span>
            {item}
          </li>
        ))}
      </ul>
      <span className={`landing-pricing-btn${popular ? ' landing-pricing-btn-popular' : ''}`}>
        {t('landing.tariffChoose')}
      </span>
    </Link>
  )
}

