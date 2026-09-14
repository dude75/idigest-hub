import { describe, expect, it, beforeEach } from 'vitest'
import type { Me } from './types'
import { clearMfaChallengeId, readMfaChallengeId, storeMfaChallengeId } from './mfa'
import { localAuthProfileVisible, resolveAuthBlockPath, resolveAuthContinuationPath } from './routes'

const baseMe: Me = {
  user: {
    id: 'u1',
    email: 'user@example.com',
    role: 'org_member',
    locale: 'en',
    auth_provider: 'local',
    default_route: 'library/audio',
    disabled: false,
    must_change_password: false,
    mfa_enabled: false,
    is_instance_admin: false,
  },
  org: {
    id: 'o1',
    name: 'Acme',
    is_personal: false,
    password_ttl_days: 0,
    mfa_required: false,
    balance: '0',
    unlimited: false,
    tariff: {
      id: 't1',
      name: 'Basic',
      unlimited: false,
      available_on_signup: true,
      archived: false,
      price_per_audio_sec: '0',
      price_per_summarize_job: '0',
      price_per_1k_summary_chars: '0',
      audio_retention_days: 0,
      api_enabled: true,
      signup_credit: '0',
      max_upload_bytes: 0,
    },
  },
  actor: null,
  mfa_enabled: false,
  mfa_required: false,
  mfa_enrollment_required: false,
  must_change_password: false,
  impersonating: false,
}

describe('mfa challenge storage', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('stores and reads challenge id', () => {
    storeMfaChallengeId('challenge-1')
    expect(readMfaChallengeId()).toBe('challenge-1')
  })

  it('clears challenge id', () => {
    storeMfaChallengeId('challenge-1')
    clearMfaChallengeId()
    expect(readMfaChallengeId()).toBeNull()
  })
})

describe('localAuthProfileVisible', () => {
  it('shows for local users when SSO is off', () => {
    expect(localAuthProfileVisible(baseMe)).toBe(true)
  })

  it('hides for SSO users when org SSO is enabled', () => {
    expect(
      localAuthProfileVisible({
        ...baseMe,
        user: { ...baseMe.user, auth_provider: 'oidc' },
        org: { ...baseMe.org!, sso: { configured: true, enabled: true, login_url: '/sso/o1' } },
      }),
    ).toBe(false)
  })

  it('shows for former SSO users when org SSO is disabled', () => {
    expect(
      localAuthProfileVisible({
        ...baseMe,
        user: { ...baseMe.user, auth_provider: 'oidc' },
        org: { ...baseMe.org!, sso: { configured: true, enabled: false, login_url: '/sso/o1' } },
      }),
    ).toBe(true)
  })

  it('hides for local org_member when SSO is enabled', () => {
    expect(
      localAuthProfileVisible({
        ...baseMe,
        org: { ...baseMe.org!, sso: { configured: true, enabled: true, login_url: '/sso/o1' } },
      }),
    ).toBe(false)
  })

  it('shows for local org_admin when SSO is enabled (break-glass)', () => {
    expect(
      localAuthProfileVisible({
        ...baseMe,
        user: { ...baseMe.user, role: 'org_admin' },
        org: { ...baseMe.org!, sso: { configured: true, enabled: true, login_url: '/sso/o1' } },
      }),
    ).toBe(true)
  })

  it('shows for local org_member when SSO is only configured', () => {
    expect(
      localAuthProfileVisible({
        ...baseMe,
        org: { ...baseMe.org!, sso: { configured: true, enabled: false, login_url: '/sso/o1' } },
      }),
    ).toBe(true)
  })
})

describe('resolveAuthBlockPath', () => {
  it('returns login when me is null', () => {
    expect(resolveAuthBlockPath(null)).toBe('/login')
  })

  it('prioritizes password change over mfa enrollment', () => {
    expect(
      resolveAuthBlockPath({
        ...baseMe,
        must_change_password: true,
        mfa_enrollment_required: true,
      }),
    ).toBe('/change-password')
  })

  it('returns enroll path when org requires mfa', () => {
    expect(resolveAuthBlockPath({ ...baseMe, mfa_enrollment_required: true })).toBe('/enroll-2fa')
  })

  it('returns null when auth is complete', () => {
    expect(resolveAuthBlockPath(baseMe)).toBeNull()
  })
})

describe('resolveAuthContinuationPath', () => {
  it('routes incomplete users to block pages', () => {
    expect(resolveAuthContinuationPath({ ...baseMe, mfa_enrollment_required: true })).toBe('/enroll-2fa')
  })

  it('routes ready org users to library', () => {
    expect(resolveAuthContinuationPath(baseMe)).toBe('/app/library/audio')
  })
})
