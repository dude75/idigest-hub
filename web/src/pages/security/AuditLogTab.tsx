import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../../api'
import { AdminPage, AdminTableCard } from '../../components/AdminSection'
import { AuditFiltersPanel, auditActionLabel } from '../../components/AuditFiltersPanel'
import { StatCard, StatGrid } from '../../components/StatCard'
import { StatsPeriodCaption } from '../../components/StatsPeriodCaption'
import type { AuditLogEntry, Org } from '../../types'
import { statsRangeForDays } from '../../util/date'
import { formatInteger, fmtDate, showError } from '../../util'

const PAGE_SIZES = [10, 50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]

type AuditListResponse = {
  items: AuditLogEntry[]
  total: number
}

function formatPayload(payload: Record<string, unknown> | null, max = 120): string {
  if (!payload) return '—'
  try {
    const text = JSON.stringify(payload)
    if (text.length <= max) return text
    return `${text.slice(0, max)}…`
  } catch {
    return '—'
  }
}

function payloadTitle(payload: Record<string, unknown> | null): string | undefined {
  if (!payload) return undefined
  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return undefined
  }
}

export function AuditLogTab() {
  const { t } = useTranslation()
  const [items, setItems] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [pageSize, setPageSize] = useState<PageSize>(10)
  const [page, setPage] = useState(0)
  const [orgs, setOrgs] = useState<Org[]>([])
  const [fromDay, setFromDay] = useState(() => statsRangeForDays(1).from)
  const [toDay, setToDay] = useState(() => statsRangeForDays(1).to)
  const [orgId, setOrgId] = useState('')
  const [userId, setUserId] = useState('')
  const [action, setAction] = useState('')
  const [exporting, setExporting] = useState(false)

  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const from = total === 0 ? 0 : safePage * pageSize + 1
  const to = Math.min(total, (safePage + 1) * pageSize)

  const query = useMemo(() => {
    const params = new URLSearchParams()
    if (fromDay) params.set('from', fromDay)
    if (toDay) params.set('to', toDay)
    if (orgId) params.set('org_id', orgId)
    if (userId) params.set('user_id', userId)
    if (action) params.set('action', action)
    params.set('limit', String(pageSize))
    params.set('offset', String(safePage * pageSize))
    return `?${params.toString()}`
  }, [fromDay, toDay, orgId, userId, action, pageSize, safePage])

  const exportQuery = useMemo(() => {
    const params = new URLSearchParams()
    if (fromDay) params.set('from', fromDay)
    if (toDay) params.set('to', toDay)
    if (orgId) params.set('org_id', orgId)
    if (userId) params.set('user_id', userId)
    if (action) params.set('action', action)
    return params.toString()
  }, [fromDay, toDay, orgId, userId, action])

  const users = useMemo(() => {
    if (!orgId) return []
    return orgs.find((o) => o.id === orgId)?.members || []
  }, [orgs, orgId])

  useEffect(() => {
    api<{ items: Org[] }>('/orgs?include_hidden=true').then((r) => setOrgs(r.items)).catch(showError)
  }, [])

  useEffect(() => {
    api<AuditListResponse>(`/instance/audit${query}`)
      .then((r) => {
        setItems(r.items)
        setTotal(r.total)
      })
      .catch(showError)
  }, [query])

  async function exportCsv() {
    setExporting(true)
    try {
      const suffix = fromDay && toDay ? `${fromDay}_${toDay}` : 'export'
      await apiDownload(`/instance/audit/export?${exportQuery}`, `audit-${suffix}.csv`)
    } catch (e) {
      showError(e)
    } finally {
      setExporting(false)
    }
  }

  return (
    <AdminPage>
      <AuditFiltersPanel
        fromDay={fromDay}
        toDay={toDay}
        onFromChange={(value) => { setFromDay(value); setPage(0) }}
        onToChange={(value) => { setToDay(value); setPage(0) }}
        orgId={orgId}
        onOrgIdChange={(value) => { setOrgId(value); setPage(0) }}
        orgs={orgs}
        userId={userId}
        onUserIdChange={(value) => { setUserId(value); setPage(0) }}
        users={users}
        action={action}
        onActionChange={(value) => { setAction(value); setPage(0) }}
      />

      <StatGrid caption={<StatsPeriodCaption fromDay={fromDay} toDay={toDay} />}>
        <StatCard label={t('audit.eventsTotal')} value={formatInteger(total)} tone="ops" />
      </StatGrid>

      <AdminTableCard>
        <div className="stats-days-head admin-table-head">
          <h2>{t('security.audit')}</h2>
          <div className="row">
            <label className="inline">
              {t('task.pageSize')}
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value) as PageSize)
                  setPage(0)
                }}
              >
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>
            <button type="button" disabled={exporting} onClick={() => void exportCsv()}>
              {exporting ? t('common.loading') : t('audit.exportCsv')}
            </button>
          </div>
        </div>

        {total === 0 ? (
          <p className="stats-empty">{t('common.empty')}</p>
        ) : (
          <div className="stats-table-wrap">
            <table className="stats-table">
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
                    <td className="stats-day">{fmtDate(entry.created_at)}</td>
                    <td>
                      <span className="badge audit-action-badge" title={entry.action}>
                        {auditActionLabel(entry.action, t)}
                      </span>
                    </td>
                    <td>{entry.actor_email || '—'}</td>
                    <td>{entry.on_behalf_of_email || '—'}</td>
                    <td className="audit-payload" title={payloadTitle(entry.payload)}>
                      <code>{formatPayload(entry.payload)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > pageSize && (
          <div className="row pager">
            <button type="button" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>
              {t('common.prev')}
            </button>
            <span className="muted">{t('task.pageRange', { from, to, total })}</span>
            <button type="button" disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>
              {t('common.next')}
            </button>
          </div>
        )}
      </AdminTableCard>
    </AdminPage>
  )
}
