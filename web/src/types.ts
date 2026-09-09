export type Locale = 'en' | 'ru' | 'es'

export type User = {
  id: string
  email: string
  locale: string
  default_route: string
  disabled: boolean
  must_change_password: boolean
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

export type Org = {
  id: string
  name: string
  is_personal: boolean
  password_ttl_days: number
  balance: string
  unlimited: boolean
  tariff: Tariff
  usage?: { total_amount: string }
  members?: User[]
}

export type Me = {
  user: User
  org: Org | null
  impersonating: boolean
  actor: User | null
  must_change_password: boolean
}

export type ShareRecord = {
  id: string
  to_user_id: string
  email: string
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
  duration_sec?: number | null
  created_at: string
  transcripts?: Transcript[]
  can_transcribe?: boolean
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
}

export type Summary = ShareBadge & {
  id: string
  org_id: string
  owner_user_id: string
  source_transcript_id: string | null
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
}

export type InstanceSettings = {
  allow_new_orgs: boolean
  public_base_url: string | null
  smtp_host: string | null
  smtp_port: number | null
  smtp_user: string | null
  smtp_configured: boolean
  smtp_from: string | null
  smtp_tls: boolean
  asr_model: string
  diarization_model: string | null
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

export type InstanceStats = JobStats & {
  orgs: number
  users: number
  tasks_queued: number
  tasks_running: number
  usage_total: string
}
