import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import type { User } from '../types'
import { mfaMemberState } from '../mfa'

type Props = {
  user: Pick<
    User,
    | 'disabled'
    | 'must_change_password'
    | 'user_agreement_status'
    | 'legal_documents_acceptance'
    | 'mfa_enabled'
    | 'mfa_configured'
    | 'auth_provider'
  >
}

function acceptedVersionLabel(user: Pick<User, 'legal_documents_acceptance'>): string | null {
  const accepted = (user.legal_documents_acceptance ?? []).filter((doc) => !doc.pending)
  if (accepted.length === 0) return null
  const versions = [...new Set(accepted.map((doc) => String(doc.accepted_version)))]
  return versions.join(', ')
}

export function UserStatusBadges({ user }: Props) {
  const { t } = useTranslation()
  const agreementStatus = user.user_agreement_status
  const versionLabel = useMemo(() => acceptedVersionLabel(user), [user])

  return (
    <>
      {user.disabled ? <span className="badge err">{t('org.statusDisabled')}</span> : null}
      {user.must_change_password ? (
        <span className="badge warn">{t('auth.badgeMustChangePassword')}</span>
      ) : null}
      {agreementStatus === 'accepted' ? (
        <span className="badge out">
          {versionLabel
            ? t('agreement.badgeAcceptedVersion', { version: versionLabel })
            : t('agreement.badgeAccepted')}
        </span>
      ) : null}
      {agreementStatus === 'pending' ? (
        <span className="badge err">{t('agreement.badgeBlocked')}</span>
      ) : null}
      <MfaMemberBadge user={user} />
    </>
  )
}

function MfaMemberBadge({
  user,
}: {
  user: Pick<User, 'mfa_enabled' | 'mfa_configured' | 'auth_provider'>
}) {
  const { t } = useTranslation()
  const state = mfaMemberState(user)
  if (state === 'on') {
    return <span className="badge out">{t('org.mfaBadgeOn')}</span>
  }
  if (state === 'pending') {
    return <span className="badge warn">{t('org.mfaBadgePending')}</span>
  }
  return null
}
