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
export type SchemaMeResponse = components['schemas']['MeResponse']
export type SchemaOrgPublicResponse = components['schemas']['OrgPublicResponse']
export type SchemaTariffListResponse = components['schemas']['TariffListResponse']
export type SchemaTariffPublic = components['schemas']['TariffPublic']
export type SchemaOrgUserResetPasswordResponse = components['schemas']['OrgUserResetPasswordResponse']
export type SchemaUsageStatsResponse = components['schemas']['UsageStatsResponse']
export type SchemaInstanceUsageStatsResponse = components['schemas']['InstanceUsageStatsResponse']
export type SchemaOrgSsoAdminResponse = components['schemas']['OrgSsoAdminResponse']
export type SchemaWorkerListResponse = components['schemas']['WorkerListResponse']
export type SchemaWorkerListItem = components['schemas']['WorkerListItem']
export type SchemaWorkerPublicResponse = components['schemas']['WorkerPublicResponse']
export type SchemaShareListResponse = components['schemas']['ShareListResponse']
export type SchemaOrgUserListResponse = components['schemas']['OrgUserListResponse']
export type SchemaUserPublic = components['schemas']['UserPublic']
export type SchemaOkStatusResponse = components['schemas']['OkStatusResponse']
export type SchemaLoginOkResponse = components['schemas']['LoginOkResponse']
export type SchemaLoginMfaRequiredResponse = components['schemas']['LoginMfaRequiredResponse']
export type SchemaInstanceSettingsResponse = components['schemas']['InstanceSettingsResponse']
export type SchemaInstanceOrgListResponse = components['schemas']['InstanceOrgListResponse']
export type SchemaInstanceOrgCreateResponse = components['schemas']['InstanceOrgCreateResponse']
export type SchemaOrgLedgerResponse = components['schemas']['OrgLedgerResponse']
export type SchemaAuditLogListResponse = components['schemas']['AuditLogListResponse']
export type SchemaOrgCaptureJitsiResponse = components['schemas']['OrgCaptureJitsiResponse']
export type SchemaOrgPublicLinkListResponse = components['schemas']['OrgPublicLinkListResponse']
export type SchemaWorkerImpactResponse = components['schemas']['WorkerImpactResponse']
export type SchemaWorkerDeleteResponse = components['schemas']['WorkerDeleteResponse']
export type SchemaWorkerProbeResponse = components['schemas']['WorkerProbeResponse']
export type SchemaTariffDeleteImpactResponse = components['schemas']['TariffDeleteImpactResponse']
export type SchemaTariffDeleteResponse = components['schemas']['TariffDeleteResponse']
export type SchemaDekListResponse = components['schemas']['DekListResponse']
export type SchemaDekPublicResponse = components['schemas']['DekPublicResponse']
export type SchemaEncryptionJobPublicResponse = components['schemas']['EncryptionJobPublicResponse']
export type SchemaEncryptionJobLatestResponse = components['schemas']['EncryptionJobLatestResponse']
export type SchemaSkillListResponse = components['schemas']['SkillListResponse']
export type SchemaSkillPublicResponse = components['schemas']['SkillPublicResponse']
export type SchemaCapturePlatformsResponse = components['schemas']['CapturePlatformsResponse']
export type SchemaImportPlatformsResponse = components['schemas']['ImportPlatformsResponse']
export type SchemaUserTagListResponse = components['schemas']['UserTagListResponse']
export type SchemaPublicSummaryResponse = components['schemas']['PublicSummaryResponse']
export type SchemaAudioCreatedResponse = components['schemas']['AudioCreatedResponse']

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
