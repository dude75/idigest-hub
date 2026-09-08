import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { User } from '../types'
import { ErrorBox } from '../util'

type Props = {
  objectType: 'audio' | 'transcript' | 'summary' | 'skill'
  objectId: string
  onClose: () => void
}

export function ShareDialog({ objectType, objectId, onClose }: Props) {
  const { t } = useTranslation()
  const [users, setUsers] = useState<User[]>([])
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    api<{ items: User[] }>('/org/users')
      .then((r) => setUsers(r.items))
      .catch(setErr)
  }, [])

  async function submit() {
    setBusy(true)
    setErr(null)
    try {
      const ids = Object.entries(picked).filter(([, v]) => v).map(([id]) => id)
      await api('/shares', { method: 'POST', body: JSON.stringify({ object_type: objectType, object_id: objectId, to_user_ids: ids }) })
      setDone(true)
    } catch (e) {
      setErr(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="card modal" onClick={(e) => e.stopPropagation()}>
        <h2>{t('share.title')}</h2>
        <p className="muted">{t('share.pick')}</p>
        <ErrorBox err={err} />
        {done && <p className="ok">{t('share.done')}</p>}
        <div className="stack">
          {users.map((u) => (
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
          <button type="button" className="primary" disabled={busy} onClick={() => void submit()}>
            {t('common.share')}
          </button>
          <button type="button" onClick={onClose}>{t('common.close')}</button>
        </div>
      </div>
    </div>
  )
}
