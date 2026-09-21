import type { Worker, WorkersListSummary } from '../../types'

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

export function normalizeCaptureCapacitySummary(
  summary: WorkersListSummary | null | undefined,
): WorkerPoolCapacity | null {
  return normalizeCapacity(summary?.capture_capacity)
}

export function normalizeTypeCapacitySummary(
  summary: WorkersListSummary | null | undefined,
  workerType: 'transcribe' | 'summarize' | 'capture',
): WorkerPoolCapacity | null {
  const raw =
    workerType === 'transcribe'
      ? summary?.transcribe_capacity
      : workerType === 'summarize'
        ? summary?.summarize_capacity
        : summary?.capture_capacity
  return normalizeCapacity(raw)
}

/** Колонка «Ёмкость»: workers.available / workers.max (или fallback hub-ноды). */
export function workerCapacityCell(
  worker: Worker,
  summary: WorkersListSummary | null | undefined,
): WorkerCapacityCell | null {
  if (worker.type === 'transcribe' || worker.type === 'summarize' || worker.type === 'capture') {
    const cap = normalizeTypeCapacitySummary(summary, worker.type)
    if (!cap) return null
    return { available: cap.available, max: cap.max }
  }
  return null
}
