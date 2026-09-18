import { describe, expect, it } from 'vitest'
import type { DateTimePrefs } from '../types'
import { formatDateTime, parseIsoUtc } from './datetimeFormat'

const iso = '2026-09-16T12:30:00.000Z'

describe('parseIsoUtc', () => {
  it('treats naive API timestamps as UTC', () => {
    const naive = '2026-09-17T23:33:35.087736'
    expect(parseIsoUtc(naive).toISOString()).toBe('2026-09-17T23:33:35.087Z')
  })
})

describe('formatDateTime', () => {
  it('formats naive UTC timestamps in user timezone', () => {
    const prefs: DateTimePrefs = {
      format: 'eu_24h',
      timezone: 'GMT+3',
      format_source: 'user',
      timezone_source: 'user',
      instance_format: 'eu_24h',
      instance_timezone: 'GMT+0',
    }
    expect(formatDateTime('2026-09-17T23:33:35.087736', prefs, 'en')).toBe('18.09.2026 02:33')
  })

  it('formats iso preset in GMT+0', () => {
    const prefs: DateTimePrefs = {
      format: 'iso',
      timezone: 'GMT+0',
      format_source: 'instance',
      timezone_source: 'instance',
      instance_format: 'iso',
      instance_timezone: 'GMT+0',
    }
    expect(formatDateTime(iso, prefs, 'en')).toBe('2026-09-16 12:30')
  })

  it('formats eu preset as DD.MM.YYYY 24h', () => {
    const prefs: DateTimePrefs = {
      format: 'eu_24h',
      timezone: 'GMT+0',
      format_source: 'instance',
      timezone_source: 'instance',
      instance_format: 'eu_24h',
      instance_timezone: 'GMT+0',
    }
    expect(formatDateTime(iso, prefs, 'en')).toBe('16.09.2026 12:30')
  })

  it('formats us preset with GMT offset shift', () => {
    const prefs: DateTimePrefs = {
      format: 'us_12h',
      timezone: 'GMT-5',
      format_source: 'user',
      timezone_source: 'user',
      instance_format: 'eu_24h',
      instance_timezone: 'GMT+0',
    }
    expect(formatDateTime(iso, prefs, 'en')).toMatch(/9\/16\/2026/)
  })
})
