import { useTranslation } from 'react-i18next'
import { ButtonLink } from '@/components/ui/button-link'
import { cn } from '@/lib/utils'

type Props = {
  className?: string
}

export function BackToLandingLink({ className }: Props) {
  const { t } = useTranslation()
  return (
    <ButtonLink to="/" variant="outline" className={cn('legal-document-back', className)}>
      {t('landing.backHome')}
    </ButtonLink>
  )
}
