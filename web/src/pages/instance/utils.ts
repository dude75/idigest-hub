import type { Worker } from '../../types'

export function healthLabel(w: Worker): string {
  const health = w.last_health
  if (!health) return '—'
  const http = health._http
  const ready = health._ready_http
  const parts = [
    w.last_seen_version || '',
    http != null ? `http ${String(http)}` : '',
    ready != null ? `ready ${String(ready)}` : '',
  ]
  const text = parts.filter(Boolean).join(' · ')
  return text || JSON.stringify(health)
}
