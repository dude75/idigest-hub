import type { Worker } from '../../types'
import type { WorkersListSummary } from '../../types'

export type CaptureSlots = {
  available: number
  max: number
  active: number
}

/** GET /health → slots (icapture). */
export function workerSlotsFromHealth(worker: Worker): CaptureSlots | null {
  const health = worker.last_health
  if (!health || typeof health !== 'object') return null
  const raw = health.slots
  if (!raw || typeof raw !== 'object') return null
  const max = Number((raw as { max?: unknown }).max)
  const available = Number((raw as { available?: unknown }).available)
  const active = Number((raw as { active?: unknown }).active)
  if (!Number.isFinite(max) || max <= 0) return null
  return {
    max,
    available: Number.isFinite(available) ? available : 0,
    active: Number.isFinite(active) ? active : 0,
  }
}

export function captureSlotsFromWorker(worker: Worker): CaptureSlots | null {
  if (worker.type !== 'capture') return null
  return workerSlotsFromHealth(worker)
}

function normalizeSlotsSummary(raw: unknown): CaptureSlots | null {
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

export function normalizeCaptureSlotsSummary(
  summary: WorkersListSummary | null | undefined,
): CaptureSlots | null {
  return normalizeSlotsSummary(summary?.capture_slots)
}

export function normalizeHubTypeSlotsSummary(
  summary: WorkersListSummary | null | undefined,
  workerType: 'transcribe' | 'summarize',
): CaptureSlots | null {
  const raw =
    workerType === 'transcribe' ? summary?.transcribe_slots : summary?.summarize_slots
  return normalizeSlotsSummary(raw)
}
