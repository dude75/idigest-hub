import { describe, expect, it } from 'vitest'
import { canStartCryptoReencrypt, isCryptoReencryptJobRunning } from './cryptoReencrypt'

describe('isCryptoReencryptJobRunning', () => {
  it('is true when running_job_id is set', () => {
    expect(isCryptoReencryptJobRunning({ items: [], running_job_id: 'j1' }, null)).toBe(true)
  })

  it('is true for queued or running latest job', () => {
    expect(isCryptoReencryptJobRunning(null, 'queued')).toBe(true)
    expect(isCryptoReencryptJobRunning(null, 'running')).toBe(true)
    expect(isCryptoReencryptJobRunning(null, 'completed')).toBe(false)
  })
})

describe('canStartCryptoReencrypt', () => {
  it('requires more than one DEK', () => {
    expect(
      canStartCryptoReencrypt({
        items: [{ status: 'active' }],
        reencrypt_available: true,
      }),
    ).toBe(false)
  })

  it('uses reencrypt_available from API when present', () => {
    expect(
      canStartCryptoReencrypt({
        items: [{ status: 'active' }, { status: 'retiring' }],
        reencrypt_available: false,
      }),
    ).toBe(false)
    expect(
      canStartCryptoReencrypt({
        items: [{ status: 'active' }, { status: 'retiring' }],
        reencrypt_available: true,
      }),
    ).toBe(true)
  })

  it('falls back to retiring status without reencrypt_available', () => {
    expect(
      canStartCryptoReencrypt({
        items: [{ status: 'active' }, { status: 'retiring' }],
      }),
    ).toBe(true)
    expect(
      canStartCryptoReencrypt({
        items: [{ status: 'active' }, { status: 'active' }],
      }),
    ).toBe(false)
  })
})
