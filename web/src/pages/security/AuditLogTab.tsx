import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../../api'
import { AdminPage, AdminTableCard } from '../../components/AdminSection'
import {
  AdminDataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  AdminTableCellHint,
  adminTableCellMuted,
  adminTableCellPrimary,
} from '../../components/app/AdminDataTable'
import { AppHoverHint } from '../../components/app/AppHoverHint'
import { AuditFiltersPanel, auditActionLabel } from '../../components/AuditFiltersPanel'
import { StatCard, StatGrid } from '../../components/StatCard'
import type { SchemaInstanceOrgListResponse } from '../../openapi'
import type { AuditLogEntry, Org } from '../../types'
import { defaultFilterRange } from '../../util/date'
import { formatInteger, fmtDate, showError } from '../../util'
import { Button } from '@/components/ui/button'
import { AppListPagination } from '../../components/app/AppListPagination'
import {
  DEFAULT_LIST_PAGE_SIZE,
  listPageBounds,
  type ListPageSize,
} from '../../components/app/selectOptions'

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
  const [pageSize, setPageSize] = useState<ListPageSize>(DEFAULT_LIST_PAGE_SIZE)
  const [page, setPage] = useState(0)
  const [orgs, setOrgs] = useState<Org[]>([])
  const [fromDay, setFromDay] = useState(() => defaultFilterRange().from)
  const [toDay, setToDay] = useState(() => defaultFilterRange().to)
  const [orgId, setOrgId] = useState('')
  const [userId, setUserId] = useState('')
  const [action, setAction] = useState('')
  const [exporting, setExporting] = useState(false)

  const { safePage } = listPageBounds(total, page, pageSize)

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
    api<SchemaInstanceOrgListResponse>('/orgs?include_hidden=true')
      .then((r) => setOrgs(r.items ?? []))
      .catch(showError)
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
        onFromChange={(value) => {
          setFromDay(value)
          setPage(0)
        }}
        onToChange={(value) => {
          setToDay(value)
          setPage(0)
        }}
        orgId={orgId}
        onOrgIdChange={(value) => {
          setOrgId(value)
          setPage(0)
        }}
        orgs={orgs}
        userId={userId}
        onUserIdChange={(value) => {
          setUserId(value)
          setPage(0)
        }}
        users={users}
        action={action}
        onActionChange={(value) => {
          setAction(value)
          setPage(0)
        }}
      />

      <StatGrid>
        <StatCard label={t('audit.eventsTotal')} value={formatInteger(total)} tone="ops" />
      </StatGrid>

      <AdminTableCard
        title={t('security.audit')}
        empty={t('common.empty')}
        isEmpty={total === 0}
        tableLayout
        actions={
          <Button type="button" size="sm" variant="outline" disabled={exporting} onClick={() => void exportCsv()}>
            {exporting ? t('common.loading') : t('audit.exportCsv')}
          </Button>
        }
      >
        {total > 0 ? (
          <>
            <AdminDataTable>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('audit.time')}</TableHead>
                  <TableHead>{t('audit.action')}</TableHead>
                  <TableHead>{t('audit.actor')}</TableHead>
                  <TableHead>{t('audit.onBehalfOf')}</TableHead>
                  <TableHead>{t('audit.payload')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className={adminTableCellMuted}>{fmtDate(entry.created_at)}</TableCell>
                    <AdminTableCellHint
                      hint={entry.action}
                      className={adminTableCellPrimary}
                      hintClassName="max-w-[14rem]"
                    >
                      {auditActionLabel(entry.action, t)}
                    </AdminTableCellHint>
                    <TableCell>{entry.actor_email || '—'}</TableCell>
                    <TableCell>{entry.on_behalf_of_email || '—'}</TableCell>
                    <TableCell className={adminTableCellMuted}>
                      {payloadTitle(entry.payload) ? (
                        <AppHoverHint
                          content={
                            <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs font-normal">
                              {payloadTitle(entry.payload)}
                            </pre>
                          }
                          contentClassName="max-w-lg"
                        >
                          <code className="block max-w-[18rem] cursor-help truncate text-xs font-normal">
                            {formatPayload(entry.payload)}
                          </code>
                        </AppHoverHint>
                      ) : (
                        <code className="block max-w-[18rem] truncate text-xs font-normal">{formatPayload(entry.payload)}</code>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </AdminDataTable>
            <AppListPagination
              htmlFor="audit-page-size"
              pageSize={pageSize}
              setPageSize={setPageSize}
              page={safePage}
              setPage={setPage}
              total={total}
            />
          </>
        ) : null}
      </AdminTableCard>
    </AdminPage>
  )
}
