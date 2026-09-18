/** Fixed GMT offsets for profile/instance selectors (UTC-12 … UTC+14). */
function buildTimezoneOptions(): string[] {
  const options: string[] = []
  for (let hours = 12; hours >= 1; hours -= 1) {
    options.push(`GMT-${hours}`)
  }
  options.push('GMT+0')
  for (let hours = 1; hours <= 14; hours += 1) {
    options.push(`GMT+${hours}`)
  }
  return options
}

export const TIMEZONE_OPTIONS = buildTimezoneOptions()

export type TimezoneOption = (typeof TIMEZONE_OPTIONS)[number]

/** Map stored GMT±N value to an IANA zone usable with Intl (fixed offset, no DST). */
export function gmtToIntlTimeZone(gmt: string): string {
  const text = (gmt || '').trim()
  if (!text || text.toUpperCase() === 'UTC' || text === 'GMT+0' || text === 'GMT-0') {
    return 'UTC'
  }
  const match = /^GMT([+-])(\d{1,2})$/.exec(text)
  if (!match) return 'UTC'
  const sign = match[1]
  const hours = match[2]
  // Etc/GMT signs are inverted relative to UTC offset.
  if (sign === '+') return `Etc/GMT-${hours}`
  return `Etc/GMT+${hours}`
}
