export function utcDay(d: Date): string {
  return d.toISOString().slice(0, 10)
}

export function statsRangeForDays(days: number): { from: string; to: string } {
  const to = new Date()
  const from = new Date(to.getTime() - (days - 1) * 86400000)
  return { from: utcDay(from), to: utcDay(to) }
}

export function datePreset(
  days: number | 'month' | 'all',
  setFrom: (value: string) => void,
  setTo: (value: string) => void,
): void {
  if (days === 'all') {
    setFrom('')
    setTo('')
    return
  }
  const to = new Date()
  if (days === 'month') {
    const start = new Date(Date.UTC(to.getUTCFullYear(), to.getUTCMonth(), 1))
    setFrom(utcDay(start))
    setTo(utcDay(to))
    return
  }
  const range = statsRangeForDays(days)
  setFrom(range.from)
  setTo(range.to)
}
