import type { Worker, WorkersListSummary } from '../../types'
import { normalizeHubTypeSlotsSummary, workerSlotsFromHealth } from './captureSlots'

export type WorkerSlotsCell = { available: number; max: number }

/** Колонка «Слоты»: capture — icapture health; transcribe/summarize — доступные узлы hub. */
export function workerSlotsCell(
  worker: Worker,
  summary: WorkersListSummary | null | undefined,
): WorkerSlotsCell | null {
  if (worker.type === 'capture') {
    const slots = workerSlotsFromHealth(worker)
    if (!slots) return null
    return { available: slots.available, max: slots.max }
  }
  if (worker.type === 'transcribe' || worker.type === 'summarize') {
    const slots = normalizeHubTypeSlotsSummary(summary, worker.type)
    if (!slots) return null
    return { available: slots.available, max: slots.max }
  }
  return null
}
