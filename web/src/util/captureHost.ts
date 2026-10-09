const IMPORT_VIDEO_HOST_SUFFIXES = ['youtube.com', 'youtu.be', 'rutube.ru', 'tiktok.com', 'tiktokv.com']

const TELEMOST_HOSTS = new Set(['telemost.yandex.ru', 'telemost.yandex.com'])

function isImportVideoHost(host: string): boolean {
  return IMPORT_VIDEO_HOST_SUFFIXES.some((d) => host === d || host.endsWith(`.${d}`))
}

export function isImportVideoUrl(url: string): boolean {
  const raw = url.trim()
  if (!/^https?:\/\//i.test(raw)) return false
  try {
    const u = new URL(raw)
    let host = u.hostname.toLowerCase()
    if (host.startsWith('www.')) host = host.slice(4)
    return isImportVideoHost(host)
  } catch {
    return false
  }
}

/** Meeting URL shape (Jitsi room, Telemost, …) — independent of capture being enabled. */
export function isMeetingCaptureUrl(url: string): boolean {
  if (isTelemostCaptureUrl(url)) return true
  if (!meetingRoomPath(url)) return false
  const host = normalizeJitsiHostInput(url)
  if (!host || isImportVideoHost(host)) return false
  return true
}

export type IngestLinkFieldMode = 'idle' | 'meeting' | 'import'

export function ingestLinkFieldMode(url: string): IngestLinkFieldMode {
  const trimmed = url.trim()
  if (!trimmed) return 'idle'
  if (isMeetingCaptureUrl(trimmed)) return 'meeting'
  if (isImportVideoUrl(trimmed)) return 'import'
  return 'idle'
}

export function ingestLinkUrlLooksInvalid(url: string): boolean {
  const trimmed = url.trim()
  if (!trimmed) return false
  if (!/^https?:\/\//i.test(trimmed)) return true
  try {
    new URL(trimmed)
    return false
  } catch {
    return true
  }
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

/** Yandex Telemost guest / private-join link. */
export function isTelemostCaptureUrl(url: string): boolean {
  const raw = url.trim()
  if (!/^https?:\/\//i.test(raw)) return false
  try {
    const u = new URL(raw)
    let host = u.hostname.toLowerCase()
    if (host.startsWith('www.')) host = host.slice(4)
    if (!TELEMOST_HOSTS.has(host)) return false
    const parts = u.pathname.split('/').filter(Boolean)
    return parts.length >= 2 && (parts[0] === 'j' || parts[0] === 'private-join') && Boolean(parts[1])
  } catch {
    return false
  }
}

/** True when URL should use POST /tasks/capture, not /tasks/import. */
export function shouldRouteImportUrlToCapture(url: string, captureEnabled: boolean): boolean {
  if (!captureEnabled) return false
  if (isTelemostCaptureUrl(url)) return true
  if (!meetingRoomPath(url)) return false
  const host = normalizeJitsiHostInput(url)
  if (!host || isImportVideoHost(host)) return false
  return true
}

/** Jitsi lobby PIN field — not used for Telemost. */
export function captureMeetingNeedsPin(url: string, captureEnabled: boolean): boolean {
  return shouldRouteImportUrlToCapture(url, captureEnabled) && !isTelemostCaptureUrl(url)
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
