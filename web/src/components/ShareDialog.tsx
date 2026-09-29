import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import type { ShareRecord, SummaryPublicLink, User } from '../types'
import { fmtDate, showError } from '../util'
import { Modal } from './Modal'
import { Button } from '@/components/ui/button'
import { AppCheckboxRow } from './app/AppFormControls'
import { AppSelect } from './app/AppSelect'
import { FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { AppUrlCopyRow } from './app/AppUrlCopyRow'

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
    } catch (e) {
      showError(e)
    } finally {
      setPublicBusy(false)
    }
  }

  return (
    <Modal onClose={onClose} title={t('share.title')} panelClassName="share-dialog sm:max-w-lg">
      <div className="flex flex-col gap-4">
      {showPublic && (
        <section className="share-section">
          <h3 className="share-section-head">{t('share.publicLink')}</h3>
          {!me?.org?.public_base_url_set ? (
            <p className="muted share-panel-meta">{t('share.publicUrlMissing')}</p>
          ) : !me?.org?.allow_public_links ? (
            <p className="muted share-panel-meta">{t('share.publicLinksDisabled')}</p>
          ) : publicLink && publicLink.url ? (
            <div className="share-panel stack">
              <AppUrlCopyRow value={publicLink.url} className="share-public-url-row" />
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
              <Button
                type="button"
                variant="outline"
                className="share-panel-action share-panel-action-block share-revoke-public"
                disabled={publicBusy}
                onClick={() => void revokePublicLink()}
              >
                {t('share.revokePublic')}
              </Button>
            </div>
          ) : (
            <div className="share-panel stack">
              <div className="share-form-row row">
                <div className="share-field">
                  <FieldLabel htmlFor="share-expiry" className="share-field-label font-normal">
                    {t('share.expiry')}
                  </FieldLabel>
                  <AppSelect
                    id="share-expiry"
                    className="share-expiry-select"
                    value={expiryDays === null ? '' : String(expiryDays)}
                    onValueChange={(v) => setExpiryDays(v === '' ? null : Number(v))}
                    options={EXPIRY_OPTIONS.map((opt) => ({
                      value: opt.days === null ? '' : String(opt.days),
                      label: t(`share.expiry_${opt.key}`),
                    }))}
                  />
                </div>
                <AppCheckboxRow
                  id="share-use-pin"
                  className="share-pin-toggle"
                  label={t('share.usePin')}
                  checked={usePin}
                  onCheckedChange={setUsePin}
                />
                {usePin ? (
                  <div className="share-pin-wrap">
                    <div className="share-field share-pin-field">
                      <FieldLabel htmlFor="share-pin" className="share-field-label font-normal">
                        PIN
                      </FieldLabel>
                      <Input
                        id="share-pin"
                        className="share-pin-input !w-[4.75rem] max-w-[4.75rem] shrink-0"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        maxLength={6}
                        value={pin}
                        onChange={(e) => setPin(e.target.value)}
                      />
                    </div>
                    <span className="muted share-pin-hint">{t('share.pinLengthHint')}</span>
                  </div>
                ) : null}
              </div>
              <Button
                type="button"
                className="share-panel-action share-panel-action-block"
                disabled={publicBusy || (usePin && pin.trim().length < 4)}
                onClick={() => void createPublicLink()}
              >
                {t('share.createPublic')}
              </Button>
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
                  <Button type="button" variant="destructive" className="share-member-action" disabled={revoking === s.id} onClick={() => void revoke(s.id)}
                  >
                    {t('share.revoke')}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {available.length > 0 && (
        <section className="share-section">
          <h3 className="share-section-head">{t('share.addMore')}</h3>
          <div className="share-panel flex flex-col gap-3">
            <p className="muted share-panel-meta">{t('share.pick')}</p>
            <div className="share-picker-list">
              {available.map((u) => (
                <AppCheckboxRow
                  key={u.id}
                  id={`share-pick-${u.id}`}
                  className="share-picker-row"
                  label={u.email}
                  checked={Boolean(picked[u.id])}
                  onCheckedChange={(checked) => setPicked((p) => ({ ...p, [u.id]: checked }))}
                />
              ))}
            </div>
          </div>
        </section>
      )}
      </div>

      <div className="share-dialog-footer">
        {available.length > 0 && (
          <Button type="button" disabled={busy || !Object.values(picked).some(Boolean)} onClick={() => void submit()}
          >
            {t('share.assign')}
          </Button>
        )}
        <Button type="button" variant="outline" className="share-dialog-close" onClick={onClose}>
          {t('common.close')}
        </Button>
      </div>
    </Modal>
  )
}
