import { describe, expect, it, vi, afterEach } from 'vitest'
import { detectDatePreset } from './datePreset'
import { utcDay } from './date'

describe('detectDatePreset', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('detects all when both empty', () => {
    expect(detectDatePreset('', '')).toBe('all')
  })

  it('detects presets when to is today', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-10T15:00:00Z'))
    const today = utcDay(new Date())
    expect(detectDatePreset(today, today)).toBe('1')
    expect(detectDatePreset(utcDay(new Date(Date.now() - 6 * 86400000)), today)).toBe('7')
    expect(detectDatePreset(utcDay(new Date(Date.UTC(2026, 2, 1))), today)).toBe('month')
  })

  it('returns null for custom ranges', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-10T15:00:00Z'))
    expect(detectDatePreset('2026-01-01', '2026-03-10')).toBe(null)
  })
})
