import { useTranslation } from 'react-i18next'
import type { Tariff } from '../types'
import { formatBytes } from '../util'

export function TariffDetails({ tariff }: { tariff: Tariff }) {
  const { t } = useTranslation()

  return (
    <ul className="tariff-points">
      <li>{t('landing.priceAudio', { price: tariff.price_per_audio_sec })}</li>
      <li>{t('landing.priceJob', { price: tariff.price_per_summarize_job })}</li>
      <li>{t('landing.priceChars', { price: tariff.price_per_1k_summary_chars })}</li>
      <li>
        {tariff.audio_retention_days > 0
          ? t('landing.retention', { days: tariff.audio_retention_days })
          : t('landing.retentionForever')}
      </li>
      <li>{tariff.api_enabled ? t('landing.apiYes') : t('landing.apiNo')}</li>
      {!tariff.unlimited && Number(tariff.signup_credit) > 0 && (
        <li>{t('landing.credit', { amount: tariff.signup_credit })}</li>
      )}
      <li>{t('landing.uploadCap', { size: formatBytes(tariff.max_upload_bytes) })}</li>
    </ul>
  )
}
