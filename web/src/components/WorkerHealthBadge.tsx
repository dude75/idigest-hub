import { useTranslation } from 'react-i18next'
import type { Worker } from '../types'
import { HubBadge, type HubBadgeTone } from './app/AdminUi'

export function workerHealthTone(w: Worker): 'ok' | 'warn' | 'na' {
  const health = w.last_health
  if (!health) return 'na'
  const http = health._http
  const ready = health._ready_http
  if (http === 200 && (ready === 200 || ready == null)) return 'ok'
  if (http != null || ready != null) return 'warn'
  return 'na'
}

const healthHubTone: Record<'ok' | 'warn' | 'na', HubBadgeTone> = {
  ok: 'success',
  warn: 'pending',
  na: 'muted',
}

export function WorkerHealthBadge({ worker }: { worker: Worker }) {
  const { t } = useTranslation()
  const tone = workerHealthTone(worker)
  const health = worker.last_health
  const http = health?._http
  const ready = health?._ready_http
  const version = worker.last_seen_version

  if (tone === 'na') {
    return <HubBadge tone="muted">{t('instance.workerHealthUnknown')}</HubBadge>
  }

  const parts: string[] = []
  if (version) parts.push(version)
  if (http != null) parts.push(`HTTP ${String(http)}`)
  if (ready != null) parts.push(`${t('instance.workerReady')} ${String(ready)}`)

  const label = tone === 'ok' ? t('instance.workerHealthOk') : t('instance.workerHealthWarn')

  return (
    <span className="worker-health-cell">
      <HubBadge tone={healthHubTone[tone]} title={parts.join(' · ')}>
        {label}
      </HubBadge>
    </span>
  )
}

export function isWorkerHealthy(worker: Worker): boolean {
  return workerHealthTone(worker) === 'ok'
}

export function isWorkerUnhealthy(worker: Worker): boolean {
  return workerHealthTone(worker) === 'warn'
}
