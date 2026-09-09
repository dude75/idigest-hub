import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { ApiError } from './api'
import i18n from './i18n'
import type { ShareBadge } from './types'

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
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export function errorText(err: unknown, t: (key: string) => string): string {
  if (err instanceof ApiError) {
    const key = `errors.${err.code}`
    const translated = t(key)
    return translated === key ? err.message || t('errors.generic') : translated
  }
  if (err instanceof Error && err.message) return err.message
  return t('errors.generic')
}

export function showError(err: unknown, opts?: { id?: string }) {
  if (!err) return
  toast.error(errorText(err, i18n.t.bind(i18n)), { id: opts?.id })
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
    <span>
      {t('wallet.balance')}: <strong>{balance}</strong>
    </span>
  )
}
