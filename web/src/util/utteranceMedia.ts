import type { Utterance } from '../types'
import { fmtMediaTime } from '../util'

const BRACKET_TS = /^\s*\[(?:(\d+):)?(\d{1,2}):(\d{2})\]\s*/
const PLAIN_TS = /^\s*(?:(\d+):)?(\d{1,2}):(\d{2})(?:\s|$)/

function parseClockParts(h: string | undefined, m: string, s: string): number | null {
  const hh = h ? parseInt(h, 10) : 0
  const mm = parseInt(m, 10)
  const ss = parseInt(s, 10)
  if (!Number.isFinite(hh) || !Number.isFinite(mm) || !Number.isFinite(ss)) return null
  if (mm >= 60 || ss >= 60) return null
  return hh * 3600 + mm * 60 + ss
}

export function parseTimestampFromText(text: string): { seconds: number; rest: string } | null {
  for (const re of [BRACKET_TS, PLAIN_TS]) {
    const m = text.match(re)
    if (!m) continue
    const seconds = parseClockParts(m[1], m[2], m[3])
    if (seconds == null) continue
    return { seconds, rest: text.slice(m[0].length) }
  }
  return null
}

function coerceSeconds(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const n = Number(value)
    if (Number.isFinite(n)) return n
  }
  return null
}

export function utteranceStart(u: Utterance): number | null {
  const direct = coerceSeconds(u.start)
  if (direct != null) return direct
  const raw = u as Record<string, unknown>
  for (const key of ['begin', 'offset', 't', 'time']) {
    const n = coerceSeconds(raw[key])
    if (n != null) return n
  }
  return parseTimestampFromText(u.text || '')?.seconds ?? null
}

export function utteranceDisplayText(u: Utterance): string {
  const text = u.text || ''
  const parsed = parseTimestampFromText(text)
  return parsed ? parsed.rest : text
}

export function utteranceTimeLabel(u: Utterance): string | null {
  const start = utteranceStart(u)
  return start == null ? null : fmtMediaTime(start)
}
