import { workerHealthTone } from '../../components/WorkerHealthBadge'
import type { Worker, WorkersListSummary, WorkersTypeSummary } from '../../types'

export type WorkerPoolCapacity = {
  available: number
  max: number
  active: number
}

export type WorkerCapacityCell = { available: number; max: number }

function normalizeCapacity(raw: unknown): WorkerPoolCapacity | null {
  if (!raw || typeof raw !== 'object') return null
  const max = Number((raw as { max?: unknown }).max)
  if (!Number.isFinite(max) || max <= 0) return null
  const available = Number((raw as { available?: unknown }).available)
  const active = Number((raw as { active?: unknown }).active)
  return {
    max,
    available: Number.isFinite(available) ? available : 0,
    active: Number.isFinite(active) ? active : 0,
  }
}

function parseWorkerHealthPool(health: Record<string, unknown> | null | undefined): WorkerPoolCapacity | null {
  if (!health) return null
  return normalizeCapacity(health.workers)
}

function workerDispatchAvailable(worker: Worker): boolean {
  if (typeof worker.dispatch_available === 'boolean') return worker.dispatch_available
  return workerHealthTone(worker) === 'ok'
}

/** Fleet transcribe/summarize: healthy enabled hub-nodes / all hub-nodes of the type (same list as the table). */
function typeHubFleetCapacity(
  workers: Worker[],
  workerType: 'transcribe' | 'summarize',
): WorkerCapacityCell | null {
  const typed = workers.filter((w) => w.type === workerType)
  if (typed.length <= 0) return null
  const available = typed.filter((w) => w.enabled && workerHealthTone(w) === 'ok').length
  return { available, max: typed.length }
}

function typeBucketFromWorkers(
  workers: Worker[],
  workerType: 'transcribe' | 'summarize' | 'capture',
): WorkersTypeSummary {
  const typed = workers.filter((worker) => worker.type === workerType)
  const enabled = typed.filter((worker) => worker.enabled)
  return {
    total: typed.length,
    enabled: enabled.length,
    available: enabled.filter((worker) => workerDispatchAvailable(worker)).length,
  }
}

export function typeWorkerBucket(
  summary: WorkersListSummary | null | undefined,
  workers: Worker[],
  workerType: 'transcribe' | 'summarize' | 'capture',
): WorkersTypeSummary {
  return summary?.by_type?.[workerType] ?? typeBucketFromWorkers(workers, workerType)
}

export function typeHubWorkerCapacity(
  workers: Worker[],
  workerType: 'transcribe' | 'summarize',
): WorkerCapacityCell | null {
  return typeHubFleetCapacity(workers, workerType)
}

export function normalizeCaptureCapacitySummary(
  summary: WorkersListSummary | null | undefined,
  workers: Worker[] = [],
): WorkerPoolCapacity | null {
  const pool = normalizeCapacity(summary?.capture_capacity)
  if (pool) return pool
  const bucket = typeWorkerBucket(summary, workers, 'capture')
  const max = bucket.enabled > 0 ? bucket.enabled : bucket.total
  if (max <= 0) return null
  return {
    max,
    available: bucket.available,
    active: Math.max(max - bucket.available, 0),
  }
}

/** Колонка «Ёмкость»: capture — health.workers на ноде; transcribe/summarize — fleet healthy/total. */
export function workerCapacityCell(
  worker: Worker,
  allWorkers: Worker[] = [],
): WorkerCapacityCell | null {
  if (worker.type === 'transcribe' || worker.type === 'summarize') {
    const pool = parseWorkerHealthPool(worker.last_health)
    if (pool) return { available: pool.available, max: pool.max }
    return typeHubFleetCapacity(allWorkers, worker.type)
  }

  if (!worker.enabled) return null

  if (worker.type === 'capture') {
    const pool = parseWorkerHealthPool(worker.last_health)
    if (pool) return { available: pool.available, max: pool.max }
    return { available: workerDispatchAvailable(worker) ? 1 : 0, max: 1 }
  }

  return null
}
