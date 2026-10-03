/**
 * API types: generated OpenAPI paths + hand-maintained response contracts.
 *
 * Regenerate: `npm run generate:api` from web/ (requires repo .venv).
 */

export type { components, operations, paths } from './schema.gen'
export type {
  AudioListResponse,
  LibraryListEnvelope,
  SummaryListResponse,
  TaskListResponse,
  TranscriptListResponse,
} from './contracts'
