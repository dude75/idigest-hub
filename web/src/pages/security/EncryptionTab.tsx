import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { AdminFormCard, AdminPage, AdminTableCard } from '../../components/AdminSection'
import {
  AdminDataTable,
  AdminTruncateHint,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  adminTableCellMuted,
  adminTableCellNum,
  adminTableCellPrimary,
  adminTableHeadNum,
} from '../../components/app/AdminDataTable'
import { AdminFormActions, AdminMetaRow, HubBadge } from '../../components/app/AdminUi'
import { StatCard, StatGrid } from '../../components/StatCard'
import type { SchemaDekListResponse, SchemaEncryptionJobLatestResponse } from '../../openapi'
import type { EncryptionJob } from '../../types'
import { formatInteger, fmtAge, fmtDate, showError } from '../../util'
import { canStartCryptoReencrypt, isCryptoReencryptJobRunning } from '../../security/cryptoReencrypt'
import { Button } from '@/components/ui/button'

function dekStatusBadge(status: string, t: (key: string, opts?: { defaultValue?: string }) => string): string {
  return t(`encryption.statusValue.${status}`, { defaultValue: status })
}

export function EncryptionTab() {
  const { t } = useTranslation()
  const [deks, setDeks] = useState<SchemaDekListResponse | null>(null)
  const [job, setJob] = useState<EncryptionJob | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api<SchemaDekListResponse>('/instance/crypto/deks')
      .then(setDeks)
      .catch(showError)
    api<SchemaEncryptionJobLatestResponse>('/instance/crypto/reencrypt/latest')
      .then((r) => setJob((r.job as EncryptionJob | null) ?? null))
      .catch(showError)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!job || (job.status !== 'queued' && job.status !== 'running')) return
    const timer = window.setInterval(() => {
      api<{ job: EncryptionJob | null }>('/instance/crypto/reencrypt/latest')
        .then((r) => {
          setJob(r.job)
          if (r.job && r.job.status !== 'queued' && r.job.status !== 'running') {
            load()
          }
        })
        .catch(showError)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [job, load])

  const jobRunning = isCryptoReencryptJobRunning(deks, job?.status)
  const canReencrypt = canStartCryptoReencrypt(deks)

  const dekItems = deks?.items ?? []

  const activeDek = useMemo(() => {
    if (!deks?.active_dek_id) return null
    return dekItems.find((d) => d.id === deks.active_dek_id) ?? null
  }, [deks, dekItems])

  const summary = useMemo(() => ({
    total: dekItems.length,
    active: activeDek ? 1 : 0,
    job: job?.status ?? '—',
  }), [deks, activeDek, job])

  async function addDek() {
    setBusy(true)
    try {
      await api('/instance/crypto/deks', { method: 'POST' })
      load()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function startReencrypt() {
    setBusy(true)
    try {
      const started = await api<EncryptionJob>('/instance/crypto/reencrypt', { method: 'POST' })
      setJob(started)
      load()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function cancelJob() {
    if (!job) return
    setBusy(true)
    try {
      await api(`/instance/crypto/reencrypt/${job.id}/cancel`, { method: 'POST' })
      load()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  function progressLabel(j: EncryptionJob): string {
    const tables = j.progress?.tables as Record<string, { total?: number; done?: number }> | undefined
    if (!tables) return dekStatusBadge(j.status, t)
    const parts = Object.entries(tables)
      .filter(([, v]) => (v.total ?? 0) > 0 || (v.done ?? 0) > 0)
      .map(([k, v]) => `${k}: ${formatInteger(v.done ?? 0)}/${formatInteger(v.total ?? 0)}`)
    return parts.length ? parts.join(' · ') : dekStatusBadge(j.status, t)
  }

  return (
    <AdminPage>
      {deks && (
        <StatGrid>
          <StatCard label={t('encryption.deksTotal')} value={formatInteger(summary.total)} tone="ops" />
          <StatCard label={t('encryption.deksActive')} value={formatInteger(summary.active)} tone="transcribe" />
          {activeDek && (
            <StatCard
              label={t('encryption.activeDekAge')}
              value={fmtAge(activeDek.created_at)}
              title={fmtDate(activeDek.created_at)}
              tone="amount"
            />
          )}
          <StatCard
            label={t('encryption.jobStatus')}
            value={dekStatusBadge(String(summary.job), t)}
            tone={jobRunning ? 'summarize' : 'ops'}
          />
        </StatGrid>
      )}

      <AdminFormCard title={t('encryption.title')} lead={t('encryption.lead')}>
        {deks && deks.hub_secret_prev_configured ? (
          <p className="text-sm text-muted-foreground">{t('encryption.hubSecretPrevHint')}</p>
        ) : null}
        {deks && deks.deks_pending_rewrap > 0 ? (
          <p className="text-sm text-destructive">{t('encryption.rewrapPending', { count: deks.deks_pending_rewrap })}</p>
        ) : null}
        <AdminFormActions>
          <Button type="button" disabled={busy || jobRunning} onClick={() => void addDek()}>
            {t('encryption.addDek')}
          </Button>
          <Button
            type="button"
            variant={canReencrypt ? 'default' : 'outline'}
            disabled={busy || jobRunning || !canReencrypt}
            onClick={() => void startReencrypt()}
          >
            {t('encryption.reencrypt')}
          </Button>
        </AdminFormActions>
      </AdminFormCard>

      {job ? (
        <AdminFormCard title={t('encryption.jobTitle')}>
          <p className="text-sm text-muted-foreground">
            {t('encryption.jobStarted')}: {fmtDate(job.started_at ?? job.created_at)}
            {job.completed_at ? (
              <>
                {' · '}
                {t('encryption.jobFinished')}: {fmtDate(job.completed_at)}
              </>
            ) : null}
          </p>
          <AdminMetaRow>
            <HubBadge
              tone={
                job.status === 'completed'
                  ? 'success'
                  : job.status === 'failed' || job.status === 'canceled'
                    ? 'warning'
                    : 'pending'
              }
            >
              {dekStatusBadge(job.status, t)}
            </HubBadge>
            <span className="text-sm text-muted-foreground">{progressLabel(job)}</span>
          </AdminMetaRow>
          {job.error ? <p className="text-sm text-destructive">{job.error}</p> : null}
          {jobRunning ? (
            <Button type="button" variant="outline" disabled={busy} onClick={() => void cancelJob()}>
              {t('encryption.cancel')}
            </Button>
          ) : null}
        </AdminFormCard>
      ) : null}

      <AdminTableCard
        title={t('encryption.deksTitle')}
        empty={t('encryption.noDeks')}
        isEmpty={dekItems.length === 0}
        tableLayout
      >
        {dekItems.length > 0 ? (
          <AdminDataTable>
            <TableHeader>
              <TableRow>
                <TableHead>{t('encryption.dekId')}</TableHead>
                <TableHead>{t('encryption.status')}</TableHead>
                <TableHead className={adminTableHeadNum}>{t('encryption.usage')}</TableHead>
                <TableHead>{t('encryption.created')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {dekItems.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className={adminTableCellPrimary}>
                    <AdminMetaRow>
                      <AdminTruncateHint hint={row.id} className="inline max-w-[8rem]">
                        <code className="text-xs">{row.id.slice(0, 8)}…</code>
                      </AdminTruncateHint>
                      {deks?.active_dek_id === row.id ? (
                        <HubBadge tone="success">{t('encryption.active')}</HubBadge>
                      ) : null}
                    </AdminMetaRow>
                  </TableCell>
                  <TableCell>
                    <HubBadge
                      tone={
                        row.status === 'active'
                          ? 'success'
                          : row.status === 'retiring'
                            ? 'pending'
                            : 'muted'
                      }
                    >
                      {dekStatusBadge(row.status, t)}
                    </HubBadge>
                  </TableCell>
                  <TableCell className={adminTableCellNum}>{formatInteger(row.usage_count)}</TableCell>
                  <TableCell className={adminTableCellMuted}>{fmtDate(row.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </AdminDataTable>
        ) : null}
      </AdminTableCard>
    </AdminPage>
  )
}
