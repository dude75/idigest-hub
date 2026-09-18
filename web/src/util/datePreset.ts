import { utcDay } from './date'

export type DatePresetId = '1' | '7' | '30' | 'month' | 'all'

export function detectDatePreset(fromDay: string, toDay: string): DatePresetId | null {
  if (!fromDay && !toDay) return 'all'
  const today = utcDay(new Date())
  if (toDay !== today) return null
  const to = new Date()
  const monthStart = utcDay(new Date(Date.UTC(to.getUTCFullYear(), to.getUTCMonth(), 1)))
  if (fromDay === monthStart) return 'month'
  if (fromDay === today) return '1'
  const from7 = utcDay(new Date(to.getTime() - 6 * 86400000))
  if (fromDay === from7) return '7'
  const from30 = utcDay(new Date(to.getTime() - 29 * 86400000))
  if (fromDay === from30) return '30'
  return null
}
