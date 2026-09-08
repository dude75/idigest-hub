import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth'
import { resolveHomePath } from '../routes'
import { useAppVersion } from '../useAppVersion'

type Props = {
  link?: boolean
}

export function AppBrand({ link = false }: Props) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const version = useAppVersion()
  const content = (
    <>
      {t('app')}
      {version && <span className="badge out">{version}</span>}
    </>
  )

  if (link) {
    return (
      <NavLink to={resolveHomePath(me)} className="brand">
        {content}
      </NavLink>
    )
  }

  return <span className="brand">{content}</span>
}
