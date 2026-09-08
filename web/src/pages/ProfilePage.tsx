import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import type { ApiToken } from '../types'
import { ErrorBox, fmtDate } from '../util'

export function ProfilePage() {
  const { t } = useTranslation()
  const { me, refresh } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [tokens, setTokens] = useState<ApiToken[]>([])
  const [tokenName, setTokenName] = useState('')
  const [secret, setSecret] = useState<string | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const [ok, setOk] = useState(false)

  async function load() {
    const r = await api<{ items: ApiToken[] }>('/auth/tokens')
    setTokens(r.items)
  }

  useEffect(() => {
    load().catch(setErr)
  }, [])

  async function changePw(e: FormEvent) {
    e.preventDefault()
    setErr(null)
    setOk(false)
    try {
      await api('/auth/password/change', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: next }),
      })
      setCurrent('')
      setNext('')
      setOk(true)
      await refresh()
    } catch (e) {
      setErr(e)
    }
  }

  async function createToken() {
    setErr(null)
    try {
      const row = await api<ApiToken>('/auth/tokens', { method: 'POST', body: JSON.stringify({ name: tokenName }) })
      setSecret(row.token || null)
      setTokenName('')
      await load()
    } catch (e) {
      setErr(e)
    }
  }

  async function revoke(id: string) {
    await api(`/auth/tokens/${id}`, { method: 'DELETE' })
    await load()
  }

  return (
    <div>
      <h1>{t('profile.title')}</h1>
      <p className="muted">{me?.user.email}</p>
      <ErrorBox err={err} />
      {ok && <p className="ok">{t('common.save')}</p>}
      <form className="card stack" onSubmit={(e) => void changePw(e)}>
        <h2>{t('auth.changePassword')}</h2>
        <label>
          {t('auth.currentPassword')}
          <input type="password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
        </label>
        <label>
          {t('auth.newPassword')}
          <input type="password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
        </label>
        <button className="primary" type="submit">{t('common.save')}</button>
      </form>
      <h2>{t('profile.tokens')}</h2>
      {!me?.org?.tariff.api_enabled && me?.org && <p className="muted">{t('profile.apiDisabled')}</p>}
      {secret && (
        <div className="card">
          <p>{t('profile.secretOnce')}</p>
          <div className="secret">{secret}</div>
        </div>
      )}
      <div className="row" style={{ margin: '8px 0' }}>
        <input placeholder={t('common.name')} value={tokenName} onChange={(e) => setTokenName(e.target.value)} />
        <button className="primary" type="button" disabled={Boolean(me?.org) && !me?.org?.tariff.api_enabled} onClick={() => void createToken()}>{t('profile.newToken')}</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>{t('common.name')}</th>
            <th>prefix</th>
            <th>{t('common.created')}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {tokens.map((tok) => (
            <tr key={tok.id}>
              <td>{tok.name} {tok.revoked && <span className="badge">{t('profile.revoked')}</span>} {tok.blocked_by_tariff && <span className="badge warn">{t('profile.blockedTariff')}</span>}</td>
              <td>{tok.prefix}</td>
              <td>{fmtDate(tok.created_at)}</td>
              <td>
                {!tok.revoked && (
                  <button type="button" className="danger" onClick={() => void revoke(tok.id)}>{t('profile.revoke')}</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
