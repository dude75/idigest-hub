/**
 * API response envelopes aligned with hub presenters.
 * OpenAPI still marks many routes as generic objects; keep canonical shapes here
 * until routers declare response_model.
 */

import type { Audio, Summary, Task, Transcript } from '../types'

export type LibraryListEnvelope<T> = {
  items: T[]
  total: number
  hidden_count: number
}

export type AudioListResponse = LibraryListEnvelope<Audio>
export type TranscriptListResponse = LibraryListEnvelope<Transcript>
export type SummaryListResponse = LibraryListEnvelope<Summary>

export type TaskListResponse = {
  active: Task[]
  done: Task[]
  done_total: number
}
