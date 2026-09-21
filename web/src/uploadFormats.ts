/** Keep in sync with app.constants ALLOWED_*_SUFFIXES. */
export const UPLOAD_AUDIO_SUFFIXES = ['.wav', '.mp3', '.m4a'] as const

export const UPLOAD_VIDEO_SUFFIXES = [
  '.mp4',
  '.m4v',
  '.mov',
  '.mkv',
  '.webm',
  '.avi',
  '.3gp',
] as const

const VIDEO_SET = new Set<string>(UPLOAD_VIDEO_SUFFIXES)

export function isVideoUploadFilename(name: string): boolean {
  const i = name.lastIndexOf('.')
  if (i < 0) return false
  return VIDEO_SET.has(name.slice(i).toLowerCase())
}

export const UPLOAD_FILE_ACCEPT = [
  ...UPLOAD_AUDIO_SUFFIXES,
  'audio/wav',
  'audio/mpeg',
  'audio/mp4',
  ...UPLOAD_VIDEO_SUFFIXES,
  'video/mp4',
  'video/quicktime',
  'video/x-matroska',
  'video/webm',
  'video/x-msvideo',
  'video/3gpp',
].join(',')
