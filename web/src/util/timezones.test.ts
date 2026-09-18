import { describe, expect, it } from 'vitest'
import { TIMEZONE_OPTIONS, gmtToIntlTimeZone } from './timezones'

describe('TIMEZONE_OPTIONS', () => {
  it('lists GMT-12 through GMT+14', () => {
    expect(TIMEZONE_OPTIONS[0]).toBe('GMT-12')
    expect(TIMEZONE_OPTIONS).toContain('GMT+0')
    expect(TIMEZONE_OPTIONS.at(-1)).toBe('GMT+14')
    expect(TIMEZONE_OPTIONS).toHaveLength(27)
  })
})

describe('gmtToIntlTimeZone', () => {
  it('maps GMT offsets to Etc/GMT zones', () => {
    expect(gmtToIntlTimeZone('GMT+0')).toBe('UTC')
    expect(gmtToIntlTimeZone('GMT+3')).toBe('Etc/GMT-3')
    expect(gmtToIntlTimeZone('GMT-5')).toBe('Etc/GMT+5')
  })
})
