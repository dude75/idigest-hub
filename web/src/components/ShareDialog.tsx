import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { ShareRecord, User } from '../types'
import { ErrorBox } from '../util'

type Props = {
  objectType: 'audio' | 'transcript' | 'summary' | 'skill'
  objectId: string
  onClose: () => void
}

export function ShareDialog({ objectType, objectId, onClose }: Props) {
  const { t } = useTranslation()
  const [users, setUsers] = useState<User[]>([])
  const [shares, setShares] = useState<ShareRecord[]>([])
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [revoking, setRevoking] = useState<string | null>(null)

  async function loadShares() {
    const r = await api<{ items: ShareRecord[] }>(
      `/shares?object_type=${encodeURIComponent(objectType)}&object_id=${encodeURIComponent(objectId)}`,
    )
    setShares(r.items)
  }

  useEffect(() => {
    Promise.all([
      api<{ items: User[] }>('/org/users'),
      loadShares(),
    ])
      .then(([orgUsers]) => setUsers(orgUsers.items))
      .catch(setErr)
  }, [objectType, objectId])

  const sharedIds = new Set(shares.map((s) => s.to_user_id))
  const available = users.filter((u) => !sharedIds.has(u.id))

  async function submit() {
    const ids = Object.entries(picked).filter(([, v]) => v).map(([id]) => id)
    if (!ids.length) return
    setBusy(true)
    setErr(null)
    try {
      await api('/shares', {
        method: 'POST',
        body: JSON.stringify({ object_type: objectType, object_id: objectId, to_user_ids: ids }),
      })
      setPicked({})
      await loadShares()
    } catch (e) {
      setErr(e)
    } finally {
      setBusy(false)
    }
  }

  async function revoke(shareId: string) {
    setRevoking(shareId)
    setErr(null)
    try {
      await api(`/shares/${shareId}`, { method: 'DELETE' })
      setShares((prev) => prev.filter((s) => s.id !== shareId))
    } catch (e) {
      setErr(e)
    } finally {
      setRevoking(null)
    }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="card modal" onClick={(e) => e.stopPropagation()}>
        <h2>{t('share.title')}</h2>
        <ErrorBox err={err} />

        <h3 style={{ marginTop: 16, marginBottom: 8, fontSize: '0.95rem' }}>{t('share.current')}</h3>
        {shares.length === 0 ? (
          <p className="muted">{t('share.none')}</p>
        ) : (
          <div className="stack">
            {shares.map((s) => (
              <div key={s.id} className="row" style={{ justifyContent: 'space-between' }}>
                <span>{s.email}</span>
                <button
                  type="button"
                  className="danger"
                  disabled={revoking === s.id}
                  onClick={() => void revoke(s.id)}
                >
                  {t('share.revoke')}
                </button>
              </div>
            ))}
          </div>
        )}

        {available.length > 0 && (
          <>
            <h3 style={{ marginTop: 16, marginBottom: 8, fontSize: '0.95rem' }}>{t('share.addMore')}</h3>
            <p className="muted">{t('share.pick')}</p>
            <div className="stack">
              {available.map((u) => (
                <label key={u.id} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={Boolean(picked[u.id])}
                    onChange={(e) => setPicked((p) => ({ ...p, [u.id]: e.target.checked }))}
                  />
                  <span>{u.email}</span>
                </label>
              ))}
            </div>
            <div className="row" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="primary"
                disabled={busy || !Object.values(picked).some(Boolean)}
                onClick={() => void submit()}
              >
                {t('common.share')}
              </button>
            </div>
          </>
        )}

        <div className="row" style={{ marginTop: 12 }}>
          <button type="button" onClick={onClose}>{t('common.close')}</button>
        </div>
      </div>
    </div>
  )
}
