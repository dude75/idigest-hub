/** Keep in sync with app/services/user_tags.py */
export const USER_TAG_MAX_PER_OBJECT = 32
export const USER_TAG_MAX_NAME_LEN = 64

/** Auto-applied on server when uploading a file from disk. Sync: app/services/source_tags.py */
export const UPLOAD_TAG = 'upload'

/** Auto-applied on server for microphone recorder uploads. Sync: app/services/source_tags.py */
export const MIC_RECORDING_TAG = 'mic'

export function normalizeUserTagName(raw: string): string {
  return raw.trim().replace(/\s+/g, ' ')
}

export function userTagNameErrorKey(name: string): 'user_tag_name_invalid' | null {
  const normalized = normalizeUserTagName(name)
  if (!normalized || normalized.length > USER_TAG_MAX_NAME_LEN) return 'user_tag_name_invalid'
  return null
}
