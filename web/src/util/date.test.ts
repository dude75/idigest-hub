import { describe, expect, it, vi, afterEach } from 'vitest'
import { datePreset, DEFAULT_FILTER_DAYS, defaultFilterRange, statsRangeForDays, utcDay } from './date'

describe('utcDay', () => {
  it('formats as YYYY-MM-DD in UTC', () => {
    expect(utcDay(new Date('2026-03-15T12:00:00Z'))).toBe('2026-03-15')
  })
})

describe('statsRangeForDays', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('spans inclusive day count', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-10T12:00:00Z'))
    expect(statsRangeForDays(7)).toEqual({ from: '2026-03-04', to: '2026-03-10' })
  })
})

describe('defaultFilterRange', () => {
  it('uses DEFAULT_FILTER_DAYS', () => {
    expect(defaultFilterRange()).toEqual(statsRangeForDays(DEFAULT_FILTER_DAYS))
  })
})

describe('datePreset', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('clears range for all', () => {
    let from = 'x'
    let to = 'y'
    datePreset('all', (v) => { from = v }, (v) => { to = v })
    expect(from).toBe('')
    expect(to).toBe('')
  })

  it('sets month start through today', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-15T12:00:00Z'))
    let from = ''
    let to = ''
    datePreset('month', (v) => { from = v }, (v) => { to = v })
    expect(from).toBe('2026-03-01')
    expect(to).toBe('2026-03-15')
  })
})
