/**
 * Library/task list types and OpenAPI schema aliases for the UI.
 *
 * Prefer `components['schemas']['…']` for one-offs; use aliases here when imported widely.
 */

import type { components } from './schema.gen'
import type { Audio, Summary, Task, Transcript } from '../types'

type Schemas = components['schemas']

export type SchemaAudioListResponse = Schemas['AudioListResponse']
export type SchemaTranscriptListResponse = Schemas['TranscriptListResponse']
export type SchemaSummaryListResponse = Schemas['SummaryListResponse']
export type SchemaTaskListResponse = Schemas['TaskListResponse']
export type SchemaTaskListItem = Schemas['TaskListItem']
export type SchemaAudioDetailResponse = Schemas['AudioDetailResponse']
export type SchemaTranscriptDetailResponse = Schemas['TranscriptDetailResponse']
export type SchemaSummaryDetailResponse = Schemas['SummaryDetailResponse']
export type SchemaTaskPurgeResponse = Schemas['TaskPurgeResponse']
export type SchemaMeResponse = Schemas['MeResponse']
export type SchemaOrgPublicResponse = Schemas['OrgPublicResponse']
export type SchemaTariffListResponse = Schemas['TariffListResponse']
export type SchemaTariffPublic = Schemas['TariffPublic']
export type SchemaOrgUserResetPasswordResponse = Schemas['OrgUserResetPasswordResponse']
export type SchemaUsageStatsResponse = Schemas['UsageStatsResponse']
export type SchemaInstanceUsageStatsResponse = Schemas['InstanceUsageStatsResponse']
export type SchemaOrgSsoAdminResponse = Schemas['OrgSsoAdminResponse']
export type SchemaWorkerListResponse = Schemas['WorkerListResponse']
export type SchemaWorkerListItem = Schemas['WorkerListItem']
export type SchemaWorkerPublicResponse = Schemas['WorkerPublicResponse']
export type SchemaShareListResponse = Schemas['ShareListResponse']
export type SchemaShareRecordBrief = Schemas['ShareRecordBrief']
export type SchemaApiTokenListResponse = Schemas['ApiTokenListResponse']
export type SchemaApiTokenPublic = Schemas['ApiTokenPublic']
export type SchemaApiTokenCreateResponse = Schemas['ApiTokenCreateResponse']
export type SchemaInstanceOrgListItem = Schemas['InstanceOrgListItem']
export type SchemaOrgUserListResponse = Schemas['OrgUserListResponse']
export type SchemaUserPublic = Schemas['UserPublic']
export type SchemaOkStatusResponse = Schemas['OkStatusResponse']
export type SchemaLoginOkResponse = Schemas['LoginOkResponse']
export type SchemaLoginMfaRequiredResponse = Schemas['LoginMfaRequiredResponse']
export type SchemaInstanceSettingsResponse = Schemas['InstanceSettingsResponse']
export type SchemaInstanceOrgListResponse = Schemas['InstanceOrgListResponse']
export type SchemaInstanceOrgCreateResponse = Schemas['InstanceOrgCreateResponse']
export type SchemaOrgLedgerResponse = Schemas['OrgLedgerResponse']
export type SchemaAuditLogListResponse = Schemas['AuditLogListResponse']
export type SchemaOrgCaptureJitsiResponse = Schemas['OrgCaptureJitsiResponse']
export type SchemaOrgPublicLinkListResponse = Schemas['OrgPublicLinkListResponse']
export type SchemaOrgPublicLinkItem = Schemas['OrgPublicLinkItem']
export type SchemaPublicLegalDocumentsResponse = Schemas['PublicLegalDocumentsResponse']
export type SchemaPublicLegalDocumentItem = Schemas['PublicLegalDocumentItem']
export type SchemaPublicLegalDocumentDetailResponse = Schemas['PublicLegalDocumentDetailResponse']
export type SchemaLegalDocumentVersionListResponse = Schemas['LegalDocumentVersionListResponse']
export type SchemaLegalDocumentVersionSummary = Schemas['LegalDocumentVersionSummary']
export type SchemaLegalDocumentVersionDetailResponse = Schemas['LegalDocumentVersionDetailResponse']
export type SchemaOwnerSummaryPublicLinkResponse = Schemas['OwnerSummaryPublicLinkResponse']
export type SchemaOwnerSummaryPublicLinkItem = Schemas['OwnerSummaryPublicLinkItem']
export type SchemaOwnerSummaryPublicLinkCreateResponse = Schemas['OwnerSummaryPublicLinkCreateResponse']
export type SchemaWorkerImpactResponse = Schemas['WorkerImpactResponse']
export type SchemaWorkerDeleteResponse = Schemas['WorkerDeleteResponse']
export type SchemaWorkerProbeResponse = Schemas['WorkerProbeResponse']
export type SchemaTariffDeleteImpactResponse = Schemas['TariffDeleteImpactResponse']
export type SchemaTariffDeleteResponse = Schemas['TariffDeleteResponse']
export type SchemaDekListResponse = Schemas['DekListResponse']
export type SchemaDekPublicResponse = Schemas['DekPublicResponse']
export type SchemaEncryptionJobPublicResponse = Schemas['EncryptionJobPublicResponse']
export type SchemaEncryptionJobLatestResponse = Schemas['EncryptionJobLatestResponse']
export type SchemaSkillListResponse = Schemas['SkillListResponse']
export type SchemaSkillPublicResponse = Schemas['SkillPublicResponse']
export type SchemaCapturePlatformsResponse = Schemas['CapturePlatformsResponse']
export type SchemaImportPlatformsResponse = Schemas['ImportPlatformsResponse']
export type SchemaUserTagListResponse = Schemas['UserTagListResponse']
export type SchemaUserTagBrief = Schemas['UserTagBrief']
export type SchemaObjectTagsResponse = Schemas['ObjectTagsResponse']
export type SchemaPublicSummaryResponse = Schemas['PublicSummaryResponse']
export type SchemaAudioCreatedResponse = Schemas['AudioCreatedResponse']

/** OpenAPI-aligned aliases used across library/skills UI. */
export type UserTag = SchemaUserTagBrief
export type Skill = SchemaSkillPublicResponse
export type ImportPlatformsResponse = SchemaImportPlatformsResponse
export type CapturePlatformsResponse = SchemaCapturePlatformsResponse
export type ShareRecord = SchemaShareRecordBrief
export type ApiToken = SchemaApiTokenPublic

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
