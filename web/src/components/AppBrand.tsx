import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { HubBadge } from './app/AdminUi'
import { useAppVersion } from '../useAppVersion'

export function AppBrand() {
  const { t } = useTranslation()
  const version = useAppVersion()

  return (
    <Link to="/" className="brand">
      {t('app')}
      {version ? (
        <HubBadge tone="success" className="ml-1.5 align-middle font-normal">
          {version}
        </HubBadge>
      ) : null}
    </Link>
  )
}
