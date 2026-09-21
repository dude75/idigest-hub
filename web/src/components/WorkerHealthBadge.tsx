import { useTranslation } from 'react-i18next'
import type { Worker } from '../types'
import { workerSlotsFromHealth } from '../pages/instance/captureSlots'

export function workerHealthTone(w: Worker): 'ok' | 'warn' | 'na' {
  const health = w.last_health
  if (!health) return 'na'
  const http = health._http
  const ready = health._ready_http
  if (http === 200 && (ready === 200 || ready == null)) return 'ok'
  if (http != null || ready != null) return 'warn'
  return 'na'
}

export function WorkerHealthBadge({ worker }: { worker: Worker }) {
  const { t } = useTranslation()
  const tone = workerHealthTone(worker)
  const health = worker.last_health
  const http = health?._http
  const ready = health?._ready_http
  const version = worker.last_seen_version

  if (tone === 'na') {
    return <span className="badge worker-health-na">{t('instance.workerHealthUnknown')}</span>
  }

  const parts: string[] = []
  if (version) parts.push(version)
  if (http != null) parts.push(`HTTP ${String(http)}`)
  if (ready != null) parts.push(`${t('instance.workerReady')} ${String(ready)}`)
  const captureSlots = workerSlotsFromHealth(worker)
  if (captureSlots) {
    parts.push(
      t('instance.workerCaptureSlotsShort', {
        available: captureSlots.available,
        max: captureSlots.max,
      }),
    )
  }

  return (
    <span className="worker-health-cell">
      <span className={`badge worker-health-${tone}`} title={parts.join(' · ')}>
        {tone === 'ok' ? t('instance.workerHealthOk') : t('instance.workerHealthWarn')}
      </span>
      {captureSlots ? (
        <span className="muted worker-health-slots">
          {t('instance.workerCaptureSlotsShort', {
            available: captureSlots.available,
            max: captureSlots.max,
          })}
        </span>
      ) : worker.type === 'capture' ? (
        <span className="muted worker-health-slots">{t('instance.workerCaptureSlotsUnknown')}</span>
      ) : null}
    </span>
  )
}

export function isWorkerHealthy(worker: Worker): boolean {
  return workerHealthTone(worker) === 'ok'
}

export function isWorkerUnhealthy(worker: Worker): boolean {
  return workerHealthTone(worker) === 'warn'
}
