import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import type { ShareRecord, SummaryPublicLink, User } from '../types'
import { fmtDate, showError } from '../util'
import { Modal } from './Modal'

type Props = {
  objectType: 'audio' | 'transcript' | 'summary' | 'skill'
  objectId: string
  /** Summary public links: only the summary owner may create/revoke. */
  canManagePublicLink?: boolean
  onClose: () => void
}

const EXPIRY_OPTIONS = [
  { days: null, key: 'never' },
  { days: 1, key: 'd1' },
  { days: 7, key: 'd7' },
  { days: 30, key: 'd30' },
  { days: 90, key: 'd90' },
  { days: 365, key: 'd365' },
] as const

export function ShareDialog({ objectType, objectId, canManagePublicLink, onClose }: Props) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [shares, setShares] = useState<ShareRecord[]>([])
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [busy, setBusy] = useState(false)
  const [revoking, setRevoking] = useState<string | null>(null)
  const [publicLink, setPublicLink] = useState<SummaryPublicLink | null>(null)
  const [publicBusy, setPublicBusy] = useState(false)
  const [expiryDays, setExpiryDays] = useState<number | null>(7)
  const [usePin, setUsePin] = useState(false)
  const [pin, setPin] = useState('')
  const [copied, setCopied] = useState(false)

  const showPublic = objectType === 'summary' && (canManagePublicLink ?? false)

  async function loadShares() {
    const r = await api<{ items: ShareRecord[] }>(
      `/shares?object_type=${encodeURIComponent(objectType)}&object_id=${encodeURIComponent(objectId)}`,
    )
    setShares(r.items)
  }

  async function loadPublicLink() {
    if (!showPublic) return
    const r = await api<{ link: SummaryPublicLink | null }>(`/summaries/${objectId}/public-link`)
    setPublicLink(r.link)
  }

  useEffect(() => {
    Promise.all([
      api<{ items: User[] }>('/org/users'),
      loadShares(),
      showPublic ? loadPublicLink() : Promise.resolve(),
    ])
      .then(([orgUsers]) => setUsers(orgUsers.items))
      .catch(showError)
  }, [objectType, objectId, showPublic])

  const sharedIds = new Set(shares.map((s) => s.to_user_id))
  const available = users.filter((u) => !sharedIds.has(u.id))

  async function submit() {
    const ids = Object.entries(picked).filter(([, v]) => v).map(([id]) => id)
    if (!ids.length) return
    setBusy(true)
    try {
      await api('/shares', {
        method: 'POST',
        body: JSON.stringify({ object_type: objectType, object_id: objectId, to_user_ids: ids }),
      })
      setPicked({})
      await loadShares()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function revoke(shareId: string) {
    setRevoking(shareId)
    try {
      await api(`/shares/${shareId}`, { method: 'DELETE' })
      setShares((prev) => prev.filter((s) => s.id !== shareId))
    } catch (e) {
      showError(e)
    } finally {
      setRevoking(null)
    }
  }

  async function createPublicLink() {
    if (usePin && pin.trim().length < 4) return
    setPublicBusy(true)
    try {
      const r = await api<{ link: SummaryPublicLink }>(`/summaries/${objectId}/public-link`, {
        method: 'POST',
        body: JSON.stringify({
          expires_in_days: expiryDays,
          pin: usePin ? pin.trim() : null,
        }),
      })
      setPublicLink(r.link)
      setPin('')
      setUsePin(false)
    } catch (e) {
      showError(e)
    } finally {
      setPublicBusy(false)
    }
  }

  async function revokePublicLink() {
    setPublicBusy(true)
    try {
      await api(`/summaries/${objectId}/public-link`, { method: 'DELETE' })
      setPublicLink(null)
      setUsePin(false)
      setPin('')
      setExpiryDays(7)
      setCopied(false)
    } catch (e) {
      showError(e)
    } finally {
      setPublicBusy(false)
    }
  }

  async function copyPublicUrl() {
    if (!publicLink?.url) return
    try {
      await navigator.clipboard.writeText(publicLink.url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <Modal onClose={onClose} panelClassName="share-dialog">
      <h2 className="share-dialog-title">{t('share.title')}</h2>

      <div className="modal-body stack">
      {showPublic && (
        <section className="share-section">
          <h3 className="share-section-head">{t('share.publicLink')}</h3>
          {!me?.org?.public_base_url_set ? (
            <p className="muted share-panel-meta">{t('share.publicUrlMissing')}</p>
          ) : !me?.org?.allow_public_links ? (
            <p className="muted share-panel-meta">{t('share.publicLinksDisabled')}</p>
          ) : publicLink && publicLink.url ? (
            <div className="share-panel stack">
              <SsoUrlRow url={publicLink.url} onCopy={() => void copyPublicUrl()} copied={copied} />
              {(publicLink.pin_required || publicLink.expires_at) && (
                <p className="muted share-panel-meta">
                  {[
                    publicLink.pin_required ? t('share.pinSeparate') : null,
                    publicLink.expires_at
                      ? t('share.expiresAt', { when: fmtDate(publicLink.expires_at) })
                      : null,
                  ].filter(Boolean).join(' · ')}
                </p>
              )}
              <button
                type="button"
                className="danger share-panel-action"
                disabled={publicBusy}
                onClick={() => void revokePublicLink()}
              >
                {t('share.revokePublic')}
              </button>
            </div>
          ) : (
            <div className="share-panel stack">
              <div className="share-form-row row">
                <label className="share-field">
                  <span className="share-field-label">{t('share.expiry')}</span>
                  <select
                    value={expiryDays === null ? '' : String(expiryDays)}
                    onChange={(e) => setExpiryDays(e.target.value === '' ? null : Number(e.target.value))}
                  >
                    {EXPIRY_OPTIONS.map((opt) => (
                      <option key={opt.key} value={opt.days === null ? '' : String(opt.days)}>
                        {t(`share.expiry_${opt.key}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="check-row share-pin-toggle">
                  <input type="checkbox" checked={usePin} onChange={(e) => setUsePin(e.target.checked)} />
                  {t('share.usePin')}
                </label>
                {usePin && (
                  <div className="share-pin-wrap">
                    <label className="share-field share-pin-field">
                      <span className="share-field-label">PIN</span>
                      <input
                        inputMode="numeric"
                        pattern="[0-9]*"
                        maxLength={6}
                        value={pin}
                        onChange={(e) => setPin(e.target.value)}
                      />
                    </label>
                    <span className="muted share-pin-hint">{t('share.pinLengthHint')}</span>
                  </div>
                )}
              </div>
              <button
                type="button"
                className="primary share-panel-action"
                disabled={publicBusy || (usePin && pin.trim().length < 4)}
                onClick={() => void createPublicLink()}
              >
                {t('share.createPublic')}
              </button>
            </div>
          )}
        </section>
      )}

      <section className="share-section">
        <h3 className="share-section-head">{t('share.current')}</h3>
        <div className="share-panel">
          {shares.length === 0 ? (
            <p className="muted share-panel-meta">{t('share.none')}</p>
          ) : (
            <div className="share-member-list">
              {shares.map((s) => (
                <div key={s.id} className="share-member-row">
                  <span className="share-member-email">{s.email}</span>
                  <button
                    type="button"
                    className="danger share-member-action"
                    disabled={revoking === s.id}
                    onClick={() => void revoke(s.id)}
                  >
                    {t('share.revoke')}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {available.length > 0 && (
        <section className="share-section">
          <h3 className="share-section-head">{t('share.addMore')}</h3>
          <div className="share-panel stack">
            <p className="muted share-panel-meta">{t('share.pick')}</p>
            <div className="share-picker-list">
              {available.map((u) => (
                <label key={u.id} className="check-row share-picker-row">
                  <input
                    type="checkbox"
                    checked={Boolean(picked[u.id])}
                    onChange={(e) => setPicked((p) => ({ ...p, [u.id]: e.target.checked }))}
                  />
                  <span>{u.email}</span>
                </label>
              ))}
            </div>
          </div>
        </section>
      )}
      </div>

      <div className="share-dialog-footer">
        {available.length > 0 && (
          <button
            type="button"
            className="primary"
            disabled={busy || !Object.values(picked).some(Boolean)}
            onClick={() => void submit()}
          >
            {t('share.assign')}
          </button>
        )}
        <button type="button" className="share-dialog-close" onClick={onClose}>{t('common.close')}</button>
      </div>
    </Modal>
  )
}

function SsoUrlRow({ url, onCopy, copied }: { url: string; onCopy: () => void; copied: boolean }) {
  const { t } = useTranslation()
  return (
    <div className="sso-url-row">
      <code className="sso-url-value" title={url}>{url}</code>
      <button type="button" className="sso-url-copy" onClick={onCopy}>
        {copied ? t('profile.copied') : t('common.copy')}
      </button>
    </div>
  )
}
