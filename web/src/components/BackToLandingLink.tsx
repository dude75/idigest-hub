import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

type Props = {
  className?: string
}

export function BackToLandingLink({ className = 'btn' }: Props) {
  const { t } = useTranslation()
  return (
    <Link to="/" className={className}>
      {t('landing.backHome')}
    </Link>
  )
}
