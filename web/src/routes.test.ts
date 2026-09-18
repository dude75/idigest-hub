import { describe, expect, it } from 'vitest'
import type { Me } from './types'
import {
  allowedDefaultRoutes,
  defaultRoutePath,
  normalizeDefaultRoute,
  resolveHomePath,
} from './routes'

const baseMe: Me = {
  user: {
    id: 'u1',
    email: 'user@example.com',
    role: 'org_member',
    locale: 'en',
    auth_provider: 'local',
    default_route: 'library/audio',
    date_time_format: null,
    timezone: null,
    asr_model: null,
    diarization_model: null,
    show_only_my_items: false,
    disabled: false,
    must_change_password: false,
    mfa_enabled: false,
    is_instance_admin: false,
  },
  date_time_prefs: {
    format: 'eu_24h',
    timezone: 'GMT+0',
    format_source: 'instance',
    timezone_source: 'instance',
    instance_format: 'eu_24h',
    instance_timezone: 'GMT+0',
  },
  transcribe_prefs: {
    asr_model: 'whisper',
    diarization_model: 'pyannote',
    asr_source: 'instance',
    diarization_source: 'instance',
    instance_asr_model: 'whisper',
    instance_diarization_model: 'pyannote',
  },
  transcribe_models: {
    asr_models: ['whisper'],
    diarization_models: ['pyannote'],
  },
  org: {
    id: 'o1',
    name: 'Acme',
    is_personal: false,
    password_ttl_days: 0,
    mfa_required: false,
    allow_public_links: true,
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
  impersonating: false,
  mfa_enabled: false,
  mfa_required: false,
  mfa_enrollment_required: false,
  user_agreement_required: false,
  user_agreement: null,
  user_agreement_version: null,
  must_change_password: false,
}

describe('normalizeDefaultRoute', () => {
  it('maps legacy library to library/audio', () => {
    expect(normalizeDefaultRoute('library')).toBe('library/audio')
  })

  it('maps legacy instance to instance/stats', () => {
    expect(normalizeDefaultRoute('instance')).toBe('instance/stats')
  })

  it('accepts library tab routes', () => {
    expect(normalizeDefaultRoute('library/summaries')).toBe('library/summaries')
  })
})

describe('defaultRoutePath', () => {
  it('maps library tabs to paths', () => {
    expect(defaultRoutePath('library/summaries')).toBe('/app/library/summaries')
    expect(defaultRoutePath('library/transcripts')).toBe('/app/library/transcripts')
    expect(defaultRoutePath('library/audio')).toBe('/app/library/audio')
  })

  it('maps instance tabs to query paths', () => {
    expect(defaultRoutePath('instance/stats')).toBe('/app/instance')
    expect(defaultRoutePath('instance/workers')).toBe('/app/instance?tab=workers')
  })

  it('maps security tabs to query paths', () => {
    expect(defaultRoutePath('security/audit')).toBe('/app/security')
    expect(defaultRoutePath('security/encryption')).toBe('/app/security?tab=encryption')
  })
})

describe('allowedDefaultRoutes', () => {
  it('includes library tabs for org members', () => {
    const routes = allowedDefaultRoutes(baseMe)
    expect(routes).toContain('library/summaries')
    expect(routes).toContain('library/transcripts')
    expect(routes).toContain('library/audio')
  })

  it('includes stats for org_admin', () => {
    const routes = allowedDefaultRoutes({ ...baseMe, user: { ...baseMe.user, role: 'org_admin' } })
    expect(routes).toContain('stats')
  })

  it('includes instance and security tabs for instance admin', () => {
    const routes = allowedDefaultRoutes({
      ...baseMe,
      user: { ...baseMe.user, role: 'org_admin', is_instance_admin: true },
    })
    expect(routes).toContain('instance/workers')
    expect(routes).toContain('security/encryption')
  })

  it('hides instance routes while impersonating', () => {
    const routes = allowedDefaultRoutes({
      ...baseMe,
      user: { ...baseMe.user, role: 'org_admin', is_instance_admin: true },
      impersonating: true,
    })
    expect(routes).not.toContain('instance/stats')
    expect(routes).not.toContain('security/audit')
  })

  it('lists library routes before tasks for org users', () => {
    const routes = allowedDefaultRoutes(baseMe)
    expect(routes[0]).toBe('library/summaries')
    expect(routes.at(-1)).toBe('tasks')
  })
})

describe('resolveHomePath', () => {
  it('uses stored default_route when allowed', () => {
    expect(
      resolveHomePath({
        ...baseMe,
        user: { ...baseMe.user, default_route: 'library/summaries' },
      }),
    ).toBe('/app/library/summaries')
  })

  it('uses instance stats for instance admin without org when no stored route applies', () => {
    expect(
      resolveHomePath({
        ...baseMe,
        org: null,
        user: { ...baseMe.user, is_instance_admin: true, default_route: 'not-a-route' },
      }),
    ).toBe('/app/instance')
  })

  it('prefers library summaries as org fallback', () => {
    expect(
      resolveHomePath({
        ...baseMe,
        user: { ...baseMe.user, default_route: 'instance/stats' },
      }),
    ).toBe('/app/library/summaries')
  })

  it('maps legacy instance default for instance admin', () => {
    expect(
      resolveHomePath({
        ...baseMe,
        user: { ...baseMe.user, role: 'org_admin', is_instance_admin: true, default_route: 'instance' },
      }),
    ).toBe('/app/instance')
  })
})
