import type { User } from './types'

const CHALLENGE_KEY = 'mfa_challenge_id'

/** Hub TOTP state for a member row (local auth only). */
export type MfaMemberState = 'off' | 'pending' | 'on'

export function mfaMemberState(
  user: Pick<User, 'mfa_enabled' | 'mfa_configured' | 'auth_provider'>,
): MfaMemberState | null {
  if (user.auth_provider !== 'local') return null
  if (user.mfa_enabled) return 'on'
  if (user.mfa_configured) return 'pending'
  return 'off'
}

/** Same predicate as POST .../reset-mfa on the API (`totp_configured`). */
export function canAdminResetMemberMfa(
  user: Pick<User, 'mfa_configured' | 'auth_provider' | 'is_instance_admin' | 'disabled'>,
  opts?: { ssoBlocksMfa?: boolean; allowInstanceAdmin?: boolean },
): boolean {
  if (user.disabled) return false
  if (user.is_instance_admin && !opts?.allowInstanceAdmin) return false
  const hubMfaApplies = user.auth_provider === 'local' || !opts?.ssoBlocksMfa
  if (!hubMfaApplies) return false
  return user.mfa_configured === true
}

export function readMfaChallengeId(): string | null {
  try {
    return sessionStorage.getItem(CHALLENGE_KEY)
  } catch {
    return null
  }
}

export function clearMfaChallengeId(): void {
  try {
    sessionStorage.removeItem(CHALLENGE_KEY)
  } catch {
    /* ignore */
  }
}

export function storeMfaChallengeId(id: string): void {
  try {
    sessionStorage.setItem(CHALLENGE_KEY, id)
  } catch {
    /* ignore */
  }
}
