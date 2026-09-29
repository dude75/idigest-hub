import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import type { User } from '../types'
import { mfaMemberState } from '../mfa'
import { HubBadge } from './app/AdminUi'

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
      {user.disabled ? <HubBadge tone="warning">{t('org.statusDisabled')}</HubBadge> : null}
      {user.must_change_password ? (
        <HubBadge tone="pending">{t('auth.badgeMustChangePassword')}</HubBadge>
      ) : null}
      {agreementStatus === 'accepted' ? (
        <HubBadge tone="success">
          {versionLabel
            ? t('agreement.badgeAcceptedVersion', { version: versionLabel })
            : t('agreement.badgeAccepted')}
        </HubBadge>
      ) : null}
      {agreementStatus === 'pending' ? (
        <HubBadge tone="warning">{t('agreement.badgeBlocked')}</HubBadge>
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
    return <HubBadge tone="success">{t('org.mfaBadgeOn')}</HubBadge>
  }
  if (state === 'pending') {
    return <HubBadge tone="pending">{t('org.mfaBadgePending')}</HubBadge>
  }
  return null
}
