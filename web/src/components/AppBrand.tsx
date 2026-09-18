import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAppVersion } from '../useAppVersion'

export function AppBrand() {
  const { t } = useTranslation()
  const version = useAppVersion()

  return (
    <Link to="/" className="brand">
      {t('app')}
      {version && <span className="badge out">{version}</span>}
    </Link>
  )
}
