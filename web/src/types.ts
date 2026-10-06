import type { components } from './openapi/schema.gen'

type Api = components['schemas']

export type Locale = 'en' | 'ru' | 'es'

export type DateTimeFormatId = 'eu_24h' | 'us_12h' | 'iso' | 'relative'

export type DateTimePrefs = {
  format: DateTimeFormatId
  timezone: string
  format_source: 'user' | 'instance'
  timezone_source: 'user' | 'instance'
  instance_format: DateTimeFormatId
  instance_timezone: string
}

/** Org member / session user shape from OpenAPI `UserPublic`. */
export type User = Api['UserPublic']

export type LegalDocumentAcceptance = {
  key: 'user_agreement' | 'personal_data_consent' | 'privacy_policy'
  accepted_version: number
  current_version: number
  pending: boolean
}

export type LegalDocumentVersionSummary = Api['LegalDocumentVersionSummary']

export type LegalDocumentVersionDetail = Api['LegalDocumentVersionDetailResponse'] & {
  key: 'user_agreement' | 'personal_data_consent' | 'privacy_policy'
}

/** Tariff row from OpenAPI `TariffPublic`. */
export type Tariff = Api['TariffPublic']

export type TariffChoice = {
  id: string
  name: string
}

export type TariffRemediationPayload = {
  tariff_id: string
}

/** Tariff delete preview from OpenAPI `TariffDeleteImpactResponse`. */
export type TariffDeleteImpact = Api['TariffDeleteImpactResponse']

export type OrgSso = {
  configured: boolean
  enabled: boolean
  login_url: string | null
}

/** Org SSO admin panel shape from OpenAPI `OrgSsoAdminResponse`. */
export type OrgSsoAdmin = Api['OrgSsoAdminResponse']

/** Org profile from OpenAPI `OrgPublicResponse` (instance list may add `hidden` / `members`). */
export type Org = Api['OrgPublicResponse'] & {
  members?: User[]
  hidden?: boolean
}

export type TranscribePrefs = {
  asr_model: string
  diarization_model: string | null
  asr_source: 'user' | 'instance'
  diarization_source: 'user' | 'instance'
  instance_asr_model: string
  instance_diarization_model: string | null
}

export type DispatchablePair = {
  asr_model: string
  diarization_model: string | null
}

export type TranscribeModels = {
  asr_models: string[]
  diarization_models: string[]
  dispatchable_pairs?: DispatchablePair[]
}

export type SummarizePrefs = {
  summarize_model: string | null
  source: 'user' | 'instance'
  instance_summarize_model: string | null
}

export type CapturePrefs = {
  capture_enabled: boolean
  bot_display_name: string
  source: 'user' | 'org' | 'default'
  org_bot_display_name: string
}

export type SummarizeModels = {
  summarize_models: string[]
}

export type SummarizeModelChoice = {
  summarize_model: string
}

/** Session `/me` payload (aligned with OpenAPI `MeResponse`; nested prefs stay explicit for UI). */
export type Me = Omit<
  Api['MeResponse'],
  | 'date_time_prefs'
  | 'transcribe_prefs'
  | 'transcribe_models'
  | 'summarize_prefs'
  | 'summarize_models'
  | 'capture_prefs'
  | 'user'
  | 'org'
  | 'actor'
  | 'legal_documents'
  | 'user_agreement'
> & {
  user: User
  org: Org | null
  actor: User | null
  date_time_prefs: DateTimePrefs
  transcribe_prefs: TranscribePrefs
  transcribe_models: TranscribeModels
  summarize_prefs: SummarizePrefs
  summarize_models: SummarizeModels
  capture_prefs: CapturePrefs
  user_agreement: { version: number; text: string } | null
  legal_documents: {
    key: 'user_agreement' | 'personal_data_consent' | 'privacy_policy'
    version: number
    text: string
    accepted_version: number
    pending: boolean
  }[] | null
}

export type ShareRecord = Api['ShareRecordBrief']

export type SummaryPublicLink = Api['OwnerSummaryPublicLinkItem']

export type OrgPublicLinkItem = Api['OrgPublicLinkItem']

export type UserTag = Api['UserTagBrief']

export type LibraryObjectType = 'audio' | 'transcript' | 'summary'

export type ShareBadge = {
  share_kind?: 'incoming' | 'outgoing' | null
  shared_by?: string
  shared_with?: string[]
  shares?: ShareRecord[]
  share_id?: string
  hidden?: boolean
  owner_email?: string | null
  edited?: boolean
  user_tags?: UserTag[]
}

export type Audio = ShareBadge & {
  id: string
  org_id: string
  owner_user_id: string
  filename: string
  source_url?: string | null
  duration_sec?: number | null
  created_at: string
  transcripts?: Transcript[]
  can_transcribe?: boolean
  has_transcript?: boolean
  has_summary?: boolean
  transcript_id?: string | null
  summary_transcript_id?: string | null
}

export type UtteranceTone = {
  valence?: number
  emotions?: Record<string, number>
}

export type CallToneSummary = {
  opening_valence?: number
  closing_valence?: number
  de_escalation?: boolean
}

export type Utterance = {
  speaker?: string
  text?: string
  start?: number
  end?: number
  tone?: UtteranceTone
}

export type Transcript = ShareBadge & {
  id: string
  org_id: string
  owner_user_id: string
  source_audio_id: string | null
  source_filename?: string | null
  title?: string | null
  display_title?: string
  created_at: string
  utterances?: Utterance[]
  summaries?: Summary[]
  has_summary?: boolean
  has_tone_analytics?: boolean
  call_summary?: CallToneSummary | null
  tone_layers?: string[] | null
}

export type Summary = ShareBadge & {
  id: string
  org_id: string
  owner_user_id: string
  source_transcript_id: string | null
  source_transcript_title?: string | null
  source_audio_id?: string | null
  skill_ids: string[]
  title?: string | null
  display_title?: string
  edited: boolean
  created_at: string
  body?: string
}

export type Task = {
  task_id: string
  type: string
  status: string
  meta: Record<string, unknown>
  max_upload_bytes?: number
  transcript_id: string | null
  summary_id: string | null
  error: { code: string } | null
  org_id?: string
  user_id?: string
  audio_id?: string | null
  source_transcript_id?: string | null
  created_at?: string
  updated_at?: string
  owner_email?: string | null
  org_name?: string | null
  audio_filename?: string | null
  skill_ids?: string[]
}

export type Skill = Api['SkillPublicResponse']

/** Listed API token (`ApiTokenPublic`); create response adds `token` via `ApiTokenCreateResponse`. */
export type ApiToken = Api['ApiTokenPublic'] & { token?: string }

/** Instance worker row from OpenAPI `WorkerListItem` / `WorkerPublicResponse`. */
export type Worker = Api['WorkerListItem']

export type WorkersTypeSummary = {
  total: number
  enabled: number
  available: number
}

export type WorkersListSummary = {
  total: number
  enabled: number
  available: number
  by_type: {
    transcribe: WorkersTypeSummary
    summarize: WorkersTypeSummary
    capture: WorkersTypeSummary
  }
  hub_limits: {
    import_max_concurrent: number
  }
  /** Sum of health.workers.* (or hub-node fallback) — same as by_type.capture. */
  capture_capacity: {
    max: number
    active: number
    available: number
  }
  transcribe_capacity: {
    max: number
    active: number
    available: number
  }
  summarize_capacity: {
    max: number
    active: number
    available: number
  }
}

export type WorkerEngineOption = {
  id: string
  status: string
  label?: string
}

export type WorkerProbeResult = {
  authorized: boolean
  health_status: number
  asr_models?: WorkerEngineOption[]
  diarization_models?: WorkerEngineOption[]
  connectors?: WorkerEngineOption[]
  summarize_model?: string | null
}

export type WorkerDeleteImpactUser = {
  id: string
  email: string
  asr_model?: string
  diarization_model?: string | null
  summarize_model?: string | null
}

export type WorkerDeleteImpactTask = {
  task_id: string
  status: string
  asr_model?: string
  diarization_model?: string | null
  summarize_model?: string | null
  on_worker?: boolean
}

export type CaptureWorkerChoice = {
  id: string
  name: string
  base_url: string
}

export type WorkerRemediationPayload = {
  asr_model?: string
  diarization_model?: string | null
  summarize_model?: string
  capture_worker_id?: string
}

export type WorkerDeleteImpact = {
  action?: 'delete' | 'change'
  worker: Pick<Worker, 'id' | 'name' | 'type' | 'enabled' | 'base_url'>
  blocking: boolean
  remaining_transcribe_workers?: number
  remaining_summarize_workers?: number
  lost_model_pairs?: DispatchablePair[]
  available_pairs?: DispatchablePair[]
  suggested_replacement?: DispatchablePair | null
  lost_summarize_models?: string[]
  available_summarize_models?: SummarizeModelChoice[]
  suggested_summarize_replacement?: SummarizeModelChoice | null
  can_remediate?: boolean
  instance_defaults_broken?: boolean
  instance_defaults?: {
    asr_model?: string
    diarization_model?: string | null
    summarize_model?: string | null
  }
  affected_users?: WorkerDeleteImpactUser[]
  affected_users_count?: number
  affected_tasks?: WorkerDeleteImpactTask[]
  affected_tasks_count?: number
  last_enabled_worker?: boolean
  capture_jitsi_hosts?: { host: string; org_id: string; org_name: string }[]
  capture_jitsi_hosts_count?: number
  capture_tasks_count?: number
  capture_losing_jitsi?: boolean
  available_capture_workers?: CaptureWorkerChoice[]
  suggested_capture_worker?: CaptureWorkerChoice | null
}

export type ImportPlatform = {
  id: string
  label: string
  domains: string[]
  enabled: boolean
}

export type PublicImportPlatform = {
  label: string
  domains: string[]
}

export type ImportPlatformsResponse = Api['ImportPlatformsResponse']

export type CaptureConnector = {
  id: string
  label: string
  enabled: boolean
  status?: string
}

export type CapturePlatformsResponse = Api['CapturePlatformsResponse']

export type OrgCaptureJitsiHost = {
  id: string
  host: string
  jwt_app_id: string | null
  jwt_secret_configured: boolean
}

export type OrgCaptureWorkerChoice = {
  id: string
  name: string
}

export type InstanceSettings = {
  allow_new_orgs: boolean
  public_base_url: string | null
  smtp_host: string | null
  smtp_port: number | null
  smtp_user: string | null
  smtp_configured: boolean
  smtp_password_configured: boolean
  smtp_from: string | null
  smtp_tls: boolean
  asr_model: string
  diarization_model: string | null
  summarize_model: string | null
  asr_models: string[]
  diarization_models: string[]
  summarize_models: string[]
  dispatchable_pairs?: DispatchablePair[]
  import_enabled: boolean
  import_platforms: ImportPlatform[]
  capture_enabled: boolean
  capture_connectors: CaptureConnector[]
  download_proxy_url: string | null
  download_proxy_configured: boolean
  download_proxy_enabled: boolean
  download_cookies_path: string | null
  import_audio_bitrate_kbps: number
  import_max_concurrent: number
  session_ttl_hours: number
  task_history_retention_days: number
  rate_limit_enabled: boolean
  rate_limit_login_email: number
  rate_limit_login_ip: number
  rate_limit_login_global: number
  rate_limit_signup_email: number
  rate_limit_signup_ip: number
  rate_limit_signup_global: number
  rate_limit_reset_email: number
  rate_limit_reset_ip: number
  rate_limit_reset_global: number
  rate_limit_reset_confirm_ip: number
  rate_limit_reset_confirm_global: number
  rate_limit_setup_ip: number
  rate_limit_setup_global: number
  rate_limit_api_user: number
  rate_limit_api_ip: number
  rate_limit_api_global: number
  rate_limit_api_tasks_user: number
  rate_limit_api_tasks_ip: number
  rate_limit_mcp_poll_user: number
  rate_limit_oauth_register_ip: number
  rate_limit_oauth_register_global: number
  rate_limit_oauth_token_ip: number
  rate_limit_oauth_token_global: number
  date_time_format: string
  timezone: string
  user_agreement_text_en: string | null
  user_agreement_text_ru: string | null
  user_agreement_text_es: string | null
  user_agreement_version: number
  user_agreement_published: boolean
  personal_data_consent_text_en: string | null
  personal_data_consent_text_ru: string | null
  personal_data_consent_text_es: string | null
  personal_data_consent_version: number
  personal_data_consent_published: boolean
  privacy_policy_text_en: string | null
  privacy_policy_text_ru: string | null
  privacy_policy_text_es: string | null
  privacy_policy_version: number
  privacy_policy_published: boolean
  landing_footer_text_en: string | null
  landing_footer_text_ru: string | null
  landing_footer_text_es: string | null
  landing_footer_published: boolean
}

export type JobStats = {
  tasks_transcribe_success: number
  tasks_summarize_success: number
  audio_transcribed_sec: number
}

export type OrgStatsDay = {
  date: string
  tasks_transcribe_success: number
  tasks_summarize_success: number
  audio_transcribed_sec: number
  summary_chars: number
  amount: string
}

export type OrgStats = Api['UsageStatsResponse']

export type DownloadProxyStatus = 'up' | 'down' | 'na'

export type InstanceSnapshot = {
  orgs: number
  users: number
  tasks_queued: number
  tasks_running: number
  download_proxy_status: DownloadProxyStatus
}

export type InstanceStats = Api['InstanceUsageStatsResponse']

export type AuditLogEntry = {
  id: string
  action: string
  actor_email: string | null
  on_behalf_of_email: string | null
  payload: Record<string, unknown> | null
  created_at: string
}

export type OrgLedgerEntry = {
  id: string
  entry_type: 'charge' | 'wallet'
  created_at: string
  amount: string
  usage_amount: string | null
  kind: string | null
  user_id: string | null
  user_email: string | null
  task_id: string | null
  actor_email: string | null
  unlimited_skip: boolean
  audio_sec: number | null
  summary_chars: number | null
}

export type OrgLedger = {
  items: OrgLedgerEntry[]
  total_spent: string
  total_topup: string
  net: string
}

export type DataEncryptionKey = {
  id: string
  status: string
  created_at: string
  retired_at: string | null
  usage_count: number
}

export type EncryptionJob = {
  id: string
  target_dek_id: string
  status: string
  progress: Record<string, unknown>
  error: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}
