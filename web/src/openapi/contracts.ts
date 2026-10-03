/**
 * Library/task list types for the UI.
 *
 * OpenAPI now exposes `AudioListResponse` and siblings from backend Pydantic models.
 * These aliases keep `types.ts` domain models (ShareBadge, etc.) on list pages.
 */

import type { components } from './schema.gen'
import type { Audio, Summary, Task, Transcript } from '../types'

export type SchemaAudioListResponse = components['schemas']['AudioListResponse']
export type SchemaTranscriptListResponse = components['schemas']['TranscriptListResponse']
export type SchemaSummaryListResponse = components['schemas']['SummaryListResponse']
export type SchemaTaskListResponse = components['schemas']['TaskListResponse']
export type SchemaTaskListItem = components['schemas']['TaskListItem']
export type SchemaAudioDetailResponse = components['schemas']['AudioDetailResponse']
export type SchemaTranscriptDetailResponse = components['schemas']['TranscriptDetailResponse']
export type SchemaSummaryDetailResponse = components['schemas']['SummaryDetailResponse']
export type SchemaTaskPurgeResponse = components['schemas']['TaskPurgeResponse']

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
