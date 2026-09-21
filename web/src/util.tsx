import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { ApiError } from './api'
import i18n from './i18n'
import { Link } from 'react-router-dom'
import { libraryPath } from './routes'
import { formatAge, formatDateTime } from './util/datetimeFormat'
import type { Audio, ShareBadge, Task, Transcript } from './types'

type TaskTranslate = (
  key: string,
  opts?: Record<string, unknown> & { defaultValue?: string },
) => string

/** Shorten long labels for tables and badges (full text goes in title). */
export function truncateLabel(text: string, maxLen = 28): string {
  const value = text.trim()
  if (value.length <= maxLen) return value
  return `${value.slice(0, Math.max(1, maxLen - 1))}…`
}

export function formatInteger(value: number, locale = i18n.language): string {
  const n = Math.round(Number(value) || 0)
  return new Intl.NumberFormat(locale).format(n)
}

export function formatDecimal(value: string | number, fractionDigits = 2, locale = i18n.language): string {
  const n = typeof value === 'string' ? Number.parseFloat(value) : value
  if (!Number.isFinite(n)) return String(value)
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(n)
}

export function fmtMediaTime(sec: number): string {
  const total = Math.max(0, Math.floor(Number(sec) || 0))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  if (h > 0) return `${h}:${pad(m)}:${pad(s)}`
  return `${pad(m)}:${pad(s)}`
}

export function formatAudioTime(
  sec: number,
  t: (key: string, opts?: Record<string, number>) => string,
): string {
  const total = Math.max(0, Math.round(Number(sec) || 0))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return t('instance.durationHms', { h, m, s })
  if (m > 0) return t('instance.durationMs', { m, s })
  return t('instance.durationS', { s })
}

export function formatBytes(bytes: number): string {
  const n = Math.max(0, Number(bytes) || 0)
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(n % (1024 * 1024) === 0 ? 0 : 1)} MB`
  return `${(n / (1024 * 1024 * 1024)).toFixed(n % (1024 * 1024 * 1024) === 0 ? 0 : 1)} GB`
}

export function fmtDate(iso: string): string {
  return formatDateTime(iso, undefined, i18n.language)
}

export function fmtAge(iso: string): string {
  return formatAge(iso, i18n.language)
}

const NON_RETRIABLE_TASK_ERRORS = new Set([
  'canceled',
  'source_deleted',
  'text_too_long',
  'payload_too_large',
  'invalid_file',
  'invalid_url',
  'proxy_unavailable',
])

export function taskIsRetriable(task: Task): boolean {
  return task.status === 'error' && !!task.error?.code && !NON_RETRIABLE_TASK_ERRORS.has(task.error.code)
}

export function taskErrorMessage(task: Task, t: TaskTranslate): string | null {
  if (!task.error) return null
  const code = task.error.code
  const meta = task.meta || {}
  if (code === 'video_unavailable' && meta.reason === 'blocked_403') {
    return t('task.blocked403')
  }
  if (code === 'video_unavailable' && meta.reason === 'proxy_misconfigured') {
    return t('task.proxyMisconfigured')
  }
  if (code === 'unsupported_host') {
    if (meta.reason === 'disabled_by_admin' && typeof meta.platform === 'string') {
      return t('task.unsupportedHostAdmin', { platform: meta.platform })
    }
    const host = typeof meta.host === 'string'
      ? meta.host
      : typeof meta.platform === 'string'
        ? meta.platform
        : ''
    return t('task.unsupportedHostUnknown', { host })
  }
  const key = `errors.${code}`
  const translated = t(key, { defaultValue: '' })
  return translated || t('task.failed')
}

export function taskErrorDetail(task: Task): string | null {
  const detail = task.meta?.error_detail
  return typeof detail === 'string' && detail.trim() ? detail.trim() : null
}

export function taskErrorDetailBrief(task: Task, maxLen = 120): string | null {
  const detail = taskErrorDetail(task)
  if (!detail) return null
  if (detail.length <= maxLen) return detail
  return `${detail.slice(0, maxLen - 3)}...`
}

export function taskYoutubeClientsTried(task: Task): string | null {
  const raw = task.meta?.youtube_clients_tried
  if (!Array.isArray(raw) || raw.length === 0) return null
  const labels = raw.map((item) => {
    if (item === null || item === undefined) return 'default'
    if (Array.isArray(item)) return item.join('+') || 'default'
    return String(item)
  })
  return labels.join(', ')
}

export function errorText(err: unknown, t: (key: string) => string): string {
  if (err instanceof ApiError) {
    if (err.message) return err.message
    const key = `errors.${err.code}`
    const translated = t(key)
    return translated === key ? t('errors.generic') : translated
  }
  if (err instanceof Error && err.message) return err.message
  return t('errors.generic')
}

export function showError(err: unknown, opts?: { id?: string }) {
  if (!err) return
  toast.error(errorText(err, i18n.t.bind(i18n)), { id: opts?.id })
}

export function AudioDerivedBadges({ audio }: { audio: Audio }) {
  const { t } = useTranslation()
  if (!audio.has_transcript && !audio.has_summary) return null
  return (
    <>
      {audio.has_transcript && (
        <Link className="badge out badge-link" to={libraryPath('transcripts', audio.id)}>
          {t('library.transcripts')}
        </Link>
      )}
      {audio.has_summary && audio.summary_transcript_id && (
        <Link className="badge out badge-link" to={libraryPath('summaries', audio.summary_transcript_id)}>
          {t('library.summaries')}
        </Link>
      )}
    </>
  )
}

export function TranscriptDerivedBadges({ transcript }: { transcript: Transcript }) {
  const { t } = useTranslation()
  if (!transcript.has_summary) return null
  return (
    <Link className="badge out badge-link" to={libraryPath('summaries', transcript.id)}>
      {t('library.summaries')}
    </Link>
  )
}

export function ShareBadges({ item, showHidden = true }: { item: ShareBadge; showHidden?: boolean }) {
  const { t } = useTranslation()
  const sharedWith =
    item.shares?.map((s) => s.email).join(', ')
    || (item.shared_with?.length ? t('library.sharedWithCount', { count: item.shared_with.length }) : null)
  return (
    <span className="row">
      {item.share_kind === 'incoming' && item.shared_by && (
        <span className="badge warn">{t('library.sharedBy', { who: item.shared_by })}</span>
      )}
      {item.share_kind === 'outgoing' && sharedWith && (
        <span className="badge out">{t('library.sharedWith', { who: sharedWith })}</span>
      )}
      {item.share_kind === 'outgoing' && !sharedWith && (
        <span className="badge out">{t('library.youShared')}</span>
      )}
      {showHidden && item.hidden && <span className="badge">{t('library.hidden')}</span>}
      {item.edited && <span className="badge">{t('summary.edited')}</span>}
    </span>
  )
}

export function WalletLabel({ unlimited, balance }: { unlimited?: boolean; balance?: string }) {
  const { t } = useTranslation()
  if (unlimited) return <strong>{t('wallet.unlimited')}</strong>
  if (balance == null) return null
  return (
    <span className="wallet-label">
      {t('wallet.balance')}: <strong>{formatDecimal(balance)}</strong>
    </span>
  )
}

