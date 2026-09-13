import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import type { AuditLogEntry, Org } from '../../types'
import { datePreset, statsRangeForDays } from '../../util/date'
import { fmtDate, showError } from '../../util'

const AUDIT_ACTIONS = [
  'instance.setup',
  'tariff.create',
  'tariff.update',
  'tariff.archive',
  'tariff.unarchive',
  'wallet.delta',
  'user.password_reset',
  'org.tariff',
  'org.tariff.self',
  'org.sso.update',
  'impersonate.start',
  'impersonate.stop',
  'user.disable',
  'user.enable',
  'user.offboard.transfer',
  'user.offboard.wipe',
  'audio.wipe',
  'transcript.wipe',
  'transcript.rename',
  'summary.update',
  'summary.delete',
] as const

function formatPayload(payload: Record<string, unknown> | null): string {
  if (!payload) return '—'
  try {
    return JSON.stringify(payload)
  } catch {
    return '—'
  }
}

export function AuditLogTab() {
  const { t } = useTranslation()
  const [items, setItems] = useState<AuditLogEntry[]>([])
  const [orgs, setOrgs] = useState<Org[]>([])
  const [fromDay, setFromDay] = useState(() => statsRangeForDays(1).from)
  const [toDay, setToDay] = useState(() => statsRangeForDays(1).to)
  const [orgId, setOrgId] = useState('')
  const [userId, setUserId] = useState('')
  const [action, setAction] = useState('')

  const query = useMemo(() => {
    const params = new URLSearchParams()
    if (fromDay) params.set('from', fromDay)
    if (toDay) params.set('to', toDay)
    if (orgId) params.set('org_id', orgId)
    if (userId) params.set('user_id', userId)
    if (action) params.set('action', action)
    const text = params.toString()
    return text ? `?${text}` : ''
  }, [fromDay, toDay, orgId, userId, action])

  const users = useMemo(() => {
    if (!orgId) return []
    return orgs.find((o) => o.id === orgId)?.members || []
  }, [orgs, orgId])

  useEffect(() => {
    api<{ items: Org[] }>('/orgs?include_hidden=true').then((r) => setOrgs(r.items)).catch(showError)
  }, [])

  useEffect(() => {
    api<{ items: AuditLogEntry[] }>(`/instance/audit${query}`)
      .then((r) => setItems(r.items))
      .catch(showError)
  }, [query])

  return (
    <div>
      <div className="card stack stats-filters">
        <div className="row wrap">
          <label>{t('stats.from')}<input type="date" value={fromDay} onChange={(e) => setFromDay(e.target.value)} /></label>
          <label>{t('stats.to')}<input type="date" value={toDay} onChange={(e) => setToDay(e.target.value)} /></label>
          <label>
            {t('instance.orgs')}
            <select
              value={orgId}
              onChange={(e) => {
                setOrgId(e.target.value)
                setUserId('')
              }}
            >
              <option value="">{t('common.all')}</option>
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>{o.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t('stats.user')}
            <select
              value={userId}
              disabled={!orgId}
              onChange={(e) => setUserId(e.target.value)}
            >
              <option value="">{t('common.all')}</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.email}</option>
              ))}
            </select>
          </label>
          <label>
            {t('audit.action')}
            <select value={action} onChange={(e) => setAction(e.target.value)}>
              <option value="">{t('common.all')}</option>
              {AUDIT_ACTIONS.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="row wrap">
          <button type="button" onClick={() => datePreset(1, setFromDay, setToDay)}>{t('stats.today')}</button>
          <button type="button" onClick={() => datePreset(7, setFromDay, setToDay)}>{t('stats.days7')}</button>
          <button type="button" onClick={() => datePreset(30, setFromDay, setToDay)}>{t('stats.days30')}</button>
          <button type="button" onClick={() => datePreset('month', setFromDay, setToDay)}>{t('stats.month')}</button>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="muted">{t('common.empty')}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>{t('audit.time')}</th>
              <th>{t('audit.action')}</th>
              <th>{t('audit.actor')}</th>
              <th>{t('audit.onBehalfOf')}</th>
              <th>{t('audit.payload')}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((entry) => (
              <tr key={entry.id}>
                <td>{fmtDate(entry.created_at)}</td>
                <td><code>{entry.action}</code></td>
                <td>{entry.actor_email || '—'}</td>
                <td>{entry.on_behalf_of_email || '—'}</td>
                <td className="muted"><code>{formatPayload(entry.payload)}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
