import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth'
import { LOCALES } from '../i18n'
import type { Locale } from '../types'

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation()
  const { setLocale } = useAuth()
  return (
    <div className="lang" role="group" aria-label="language">
      {LOCALES.map((lng) => (
        <button
          key={lng}
          type="button"
          className={i18n.language === lng ? 'active' : ''}
          onClick={() => void setLocale(lng as Locale)}
        >
          {t(`lang.${lng}`)}
        </button>
      ))}
    </div>
  )
}
