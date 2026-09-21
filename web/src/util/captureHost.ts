const IMPORT_VIDEO_HOST_SUFFIXES = ['youtube.com', 'youtu.be', 'rutube.ru', 'tiktok.com', 'tiktokv.com']

function isImportVideoHost(host: string): boolean {
  return IMPORT_VIDEO_HOST_SUFFIXES.some((d) => host === d || host.endsWith(`.${d}`))
}

/** Meeting link with a room path (not a bare server URL). */
export function meetingRoomPath(url: string): string | null {
  const raw = url.trim()
  if (!/^https?:\/\//i.test(raw)) return null
  try {
    const u = new URL(raw)
    const segments = u.pathname.split('/').filter(Boolean)
    if (segments.length === 0) return null
    return segments[segments.length - 1] || null
  } catch {
    return null
  }
}

/** True when URL should use POST /tasks/capture, not /tasks/import. */
export function shouldRouteImportUrlToCapture(url: string, captureEnabled: boolean): boolean {
  if (!captureEnabled) return false
  if (!meetingRoomPath(url)) return false
  const host = normalizeJitsiHostInput(url)
  if (!host || isImportVideoHost(host)) return false
  return true
}

/** Normalize Jitsi host field (hostname only; accepts pasted meeting URLs). */
export function normalizeJitsiHostInput(raw: string): string {
  const value = raw.trim()
  if (!value) return ''
  try {
    const url = value.includes('://') ? new URL(value) : new URL(`https://${value}`)
    let host = url.hostname.toLowerCase()
    if (host.startsWith('www.')) host = host.slice(4)
    return host
  } catch {
    const host = value.split('/')[0].split('?')[0].trim().toLowerCase()
    if (host.startsWith('www.')) return host.slice(4)
    return host
  }
}
