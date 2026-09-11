export const MAX_UPLOAD = 1073741824
export const DEFAULT_IMPORT_AUDIO_BITRATE_KBPS = 64

export type InstanceTab = 'workers' | 'tariffs' | 'orgs' | 'settings' | 'baseSkills' | 'stats'

export const INSTANCE_TABS: InstanceTab[] = ['stats', 'workers', 'tariffs', 'orgs', 'settings', 'baseSkills']

export function resolveInstanceTab(tabParam: string | null): InstanceTab {
  return INSTANCE_TABS.includes(tabParam as InstanceTab) ? (tabParam as InstanceTab) : 'stats'
}

export const emptyWorker = {
  type: 'transcribe',
  name: '',
  base_url: '',
  api_token: '',
  weight: 1,
  enabled: true,
}

export const emptyTariff = {
  name: '',
  unlimited: false,
  available_on_signup: false,
  price_per_audio_sec: '0',
  price_per_summarize_job: '0',
  price_per_1k_summary_chars: '0',
  audio_retention_days: 0,
  api_enabled: true,
  signup_credit: '0',
  max_upload_bytes: MAX_UPLOAD,
}
