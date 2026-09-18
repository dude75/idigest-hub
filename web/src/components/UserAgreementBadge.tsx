import { useTranslation } from 'react-i18next'
import type { User } from '../types'

type Props = {
  user: Pick<User, 'disabled' | 'must_change_password' | 'user_agreement_status'>
}

export function UserStatusBadges({ user }: Props) {
  const { t } = useTranslation()
  const agreementStatus = user.user_agreement_status

  return (
    <>
      {user.disabled ? <span className="badge err">{t('org.statusDisabled')}</span> : null}
      {user.must_change_password ? (
        <span className="badge warn">{t('auth.badgeMustChangePassword')}</span>
      ) : null}
      {agreementStatus === 'accepted' ? (
        <span className="badge out">{t('agreement.badgeAccepted')}</span>
      ) : null}
      {agreementStatus === 'pending' ? (
        <span className="badge err">{t('agreement.badgeBlocked')}</span>
      ) : null}
    </>
  )
}
