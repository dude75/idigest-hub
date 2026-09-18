import type { DateTimeFormatId, DateTimePrefs } from '../types'
import { gmtToIntlTimeZone } from './timezones'

export const DATE_TIME_FORMATS: DateTimeFormatId[] = ['eu_24h', 'us_12h', 'iso', 'relative']

export const DEFAULT_DATE_TIME_PREFS: DateTimePrefs = {
  format: 'eu_24h',
  timezone: 'GMT+0',
  format_source: 'instance',
  timezone_source: 'instance',
  instance_format: 'eu_24h',
  instance_timezone: 'GMT+0',
}

let activePrefs: DateTimePrefs = DEFAULT_DATE_TIME_PREFS

export function setDateTimePrefs(prefs: DateTimePrefs | null | undefined): void {
  activePrefs = prefs ?? DEFAULT_DATE_TIME_PREFS
}

export function getDateTimePrefs(): DateTimePrefs {
  return activePrefs
}

/** API timestamps are UTC; naive ISO strings must not be parsed as local time. */
export function parseIsoUtc(iso: string): Date {
  const text = iso.trim()
  if (!text) return new Date(Number.NaN)
  if (/[zZ]$/.test(text) || /[+-]\d{2}:\d{2}(:\d{2})?$/.test(text)) {
    return new Date(text)
  }
  return new Date(`${text}Z`)
}

function formatPartsLocal(
  date: Date,
  timeZone: string,
  layout: 'iso' | 'eu',
): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? ''
  const y = pick('year')
  const m = pick('month')
  const d = pick('day')
  const time = `${pick('hour')}:${pick('minute')}`
  if (layout === 'iso') return `${y}-${m}-${d} ${time}`
  return `${d}.${m}.${y} ${time}`
}

export function formatAge(iso: string, locale = 'en'): string {
  const date = parseIsoUtc(iso)
  if (Number.isNaN(date.getTime())) return iso
  return formatRelative(date, locale)
}

function formatRelative(date: Date, locale: string): string {
  const now = Date.now()
  const diffSec = Math.round((date.getTime() - now) / 1000)
  const abs = Math.abs(diffSec)
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  if (abs < 60) return rtf.format(diffSec, 'second')
  const diffMin = Math.round(diffSec / 60)
  if (Math.abs(diffMin) < 60) return rtf.format(diffMin, 'minute')
  const diffHour = Math.round(diffSec / 3600)
  if (Math.abs(diffHour) < 48) return rtf.format(diffHour, 'hour')
  const diffDay = Math.round(diffSec / 86400)
  if (Math.abs(diffDay) < 30) return rtf.format(diffDay, 'day')
  const diffMonth = Math.round(diffSec / (86400 * 30))
  if (Math.abs(diffMonth) < 12) return rtf.format(diffMonth, 'month')
  return rtf.format(Math.round(diffSec / (86400 * 365)), 'year')
}

export function formatDateTime(iso: string, prefs: DateTimePrefs = activePrefs, locale = 'en'): string {
  try {
    const date = parseIsoUtc(iso)
    if (Number.isNaN(date.getTime())) return iso

    if (prefs.format === 'relative') {
      return formatRelative(date, locale)
    }

    const intlTimeZone = gmtToIntlTimeZone(prefs.timezone)

    if (prefs.format === 'iso') {
      return formatPartsLocal(date, intlTimeZone, 'iso')
    }

    if (prefs.format === 'eu_24h') {
      return formatPartsLocal(date, intlTimeZone, 'eu')
    }

    const options: Intl.DateTimeFormatOptions = {
      timeZone: intlTimeZone,
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    }
    return new Intl.DateTimeFormat('en-US', options).format(date)
  } catch {
    return iso
  }
}
