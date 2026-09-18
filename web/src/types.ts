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

export type User = {
  id: string
  email: string
  locale: string
  default_route: string
  date_time_format: string | null
  timezone: string | null
  asr_model: string | null
  diarization_model: string | null
  disabled: boolean
  must_change_password: boolean
  mfa_enabled: boolean
  mfa_configured?: boolean
  is_instance_admin: boolean
  role: string | null
  auth_provider: string
}

export type Tariff = {
  id: string
  name: string
  unlimited: boolean
  available_on_signup: boolean
  archived: boolean
  price_per_audio_sec: string
  price_per_summarize_job: string
  price_per_1k_summary_chars: string
  audio_retention_days: number
  api_enabled: boolean
  signup_credit: string
  max_upload_bytes: number
  org_count?: number
}

export type OrgSso = {
  configured: boolean
  enabled: boolean
  login_url: string | null
}

export type OrgSsoAdmin = OrgSso & {
  org_id: string
  callback_url: string | null
  public_base_url_set: boolean
  issuer: string | null
  client_id: string | null
  has_client_secret: boolean
}

export type Org = {
  id: string
  name: string
  is_personal: boolean
  password_ttl_days: number
  mfa_required: boolean
  allow_public_links: boolean
  public_base_url_set?: boolean
  balance: string
  unlimited: boolean
  tariff: Tariff
  usage?: { total_amount: string }
  members?: User[]
  sso?: OrgSso
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

export type Me = {
  user: User
  org: Org | null
  impersonating: boolean
  actor: User | null
  date_time_prefs: DateTimePrefs
  transcribe_prefs: TranscribePrefs
  transcribe_models: TranscribeModels
  must_change_password: boolean
  mfa_enabled: boolean
  mfa_required: boolean
  mfa_enrollment_required: boolean
}

export type ShareRecord = {
  id: string
  to_user_id: string
  email: string
}

export type SummaryPublicLink = {
  id: string
  summary_id: string
  url: string | null
  expires_at: string | null
  pin_required: boolean
  created_at: string
  revoked?: boolean
}

export type OrgPublicLinkItem = {
  id: string
  summary_id: string
  summary_title: string
  owner_email: string
  url: string | null
  expires_at: string | null
  pin_required: boolean
  created_at: string
  active: boolean
}

export type ShareBadge = {
  share_kind?: 'incoming' | 'outgoing' | null
  shared_by?: string
  shared_with?: string[]
  shares?: ShareRecord[]
  share_id?: string
  hidden?: boolean
  owner_email?: string | null
  edited?: boolean
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

export type Utterance = {
  speaker?: string
  text?: string
  start?: number
  end?: number
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
}

export type Skill = {
  id: string
  scope: string
  org_id: string | null
  owner_user_id: string | null
  name: string
  body: string
  created_at: string
  updated_at: string
  catalog?: string
  readonly?: boolean
  share_kind?: string
}

export type ApiToken = {
  id: string
  name: string
  prefix: string
  revoked: boolean
  blocked_by_tariff?: boolean
  created_at: string
  token?: string
}

export type Worker = {
  id: string
  type: string
  name: string
  base_url: string
  weight: number
  enabled: boolean
  last_health: Record<string, unknown> | null
  last_seen_version: string | null
  last_health_at: string | null
  asr_models: string[]
  diarization_models: string[]
}

export type WorkerEngineOption = {
  id: string
  status: string
}

export type WorkerProbeResult = {
  authorized: boolean
  health_status: number
  asr_models?: WorkerEngineOption[]
  diarization_models?: WorkerEngineOption[]
}

export type WorkerDeleteImpactUser = {
  id: string
  email: string
  asr_model: string
  diarization_model: string | null
}

export type WorkerDeleteImpactTask = {
  task_id: string
  status: string
  asr_model?: string
  diarization_model?: string | null
  on_worker?: boolean
}

export type WorkerRemediationPayload = {
  asr_model: string
  diarization_model: string | null
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
  can_remediate?: boolean
  instance_defaults_broken?: boolean
  instance_defaults?: { asr_model: string; diarization_model: string | null }
  affected_users?: WorkerDeleteImpactUser[]
  affected_users_count?: number
  affected_tasks?: WorkerDeleteImpactTask[]
  affected_tasks_count?: number
  last_enabled_worker?: boolean
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

export type ImportPlatformsResponse = {
  enabled: boolean
  platforms: PublicImportPlatform[]
  download_proxy_required: boolean
  download_proxy_available: boolean
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
  asr_models: string[]
  diarization_models: string[]
  dispatchable_pairs?: DispatchablePair[]
  import_enabled: boolean
  import_platforms: ImportPlatform[]
  download_proxy_url: string | null
  download_proxy_configured: boolean
  download_proxy_enabled: boolean
  download_cookies_path: string | null
  import_audio_bitrate_kbps: number
  session_ttl_hours: number
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
  date_time_format: string
  timezone: string
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

export type OrgStats = JobStats & {
  summary_chars: number
  total_amount: string
  days: OrgStatsDay[]
}

export type DownloadProxyStatus = 'up' | 'down' | 'na'

export type InstanceSnapshot = {
  orgs: number
  users: number
  tasks_queued: number
  tasks_running: number
  download_proxy_status: DownloadProxyStatus
}

export type InstanceStats = JobStats &
  InstanceSnapshot & {
    usage_total: string
    summary_chars: number
    days: OrgStatsDay[]
  }

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
