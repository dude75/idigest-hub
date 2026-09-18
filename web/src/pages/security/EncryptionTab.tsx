import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { AdminPage, AdminTableCard } from '../../components/AdminSection'
import { StatCard, StatGrid } from '../../components/StatCard'
import type { DataEncryptionKey, EncryptionJob } from '../../types'
import { formatInteger, fmtAge, fmtDate, showError } from '../../util'

type DekList = {
  active_dek_id: string | null
  items: DataEncryptionKey[]
  running_job_id: string | null
  deks_pending_rewrap: number
  hub_secret_prev_configured: boolean
}

function dekStatusBadge(status: string, t: (key: string, opts?: { defaultValue?: string }) => string): string {
  return t(`encryption.statusValue.${status}`, { defaultValue: status })
}

export function EncryptionTab() {
  const { t } = useTranslation()
  const [deks, setDeks] = useState<DekList | null>(null)
  const [job, setJob] = useState<EncryptionJob | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api<DekList>('/instance/crypto/deks')
      .then(setDeks)
      .catch(showError)
    api<{ job: EncryptionJob | null }>('/instance/crypto/reencrypt/latest')
      .then((r) => setJob(r.job))
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

  const retiring = deks?.items.some((d) => d.status === 'retiring') ?? false
  const jobRunning = job?.status === 'queued' || job?.status === 'running'

  const activeDek = useMemo(() => {
    if (!deks?.active_dek_id) return null
    return deks.items.find((d) => d.id === deks.active_dek_id) ?? null
  }, [deks])

  const summary = useMemo(() => ({
    total: deks?.items.length ?? 0,
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

      <div className="card stack admin-form-card">
        <div className="stats-section-head">
          <h2>{t('encryption.title')}</h2>
        </div>
        <p className="admin-lead">{t('encryption.lead')}</p>
        {deks && deks.hub_secret_prev_configured && (
          <p className="hint">{t('encryption.hubSecretPrevHint')}</p>
        )}
        {deks && deks.deks_pending_rewrap > 0 && (
          <p className="error">{t('encryption.rewrapPending', { count: deks.deks_pending_rewrap })}</p>
        )}
        <div className="row wrap">
          <button type="button" disabled={busy || jobRunning} onClick={() => void addDek()}>
            {t('encryption.addDek')}
          </button>
          <button type="button" disabled={busy || jobRunning || !retiring} onClick={() => void startReencrypt()}>
            {t('encryption.reencrypt')}
          </button>
        </div>
      </div>

      {job && (
        <div className="card stack admin-table-card">
          <div className="stats-section-head">
            <h2>{t('encryption.jobTitle')}</h2>
          </div>
          <p className="muted">
            {t('encryption.jobStarted')}: {fmtDate(job.started_at ?? job.created_at)}
            {job.completed_at && (
              <>
                {' · '}
                {t('encryption.jobFinished')}: {fmtDate(job.completed_at)}
              </>
            )}
          </p>
          <p>
            <span className={`badge encryption-job-${job.status}`}>{dekStatusBadge(job.status, t)}</span>
            {' '}
            {progressLabel(job)}
          </p>
          {job.error && <p className="error">{job.error}</p>}
          {jobRunning && (
            <button type="button" disabled={busy} onClick={() => void cancelJob()}>
              {t('encryption.cancel')}
            </button>
          )}
        </div>
      )}

      <AdminTableCard title={t('encryption.deksTitle')} empty={t('encryption.noDeks')} isEmpty={!deks?.items.length}>
        {deks && deks.items.length > 0 ? (
          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>{t('encryption.dekId')}</th>
                  <th>{t('encryption.status')}</th>
                  <th className="num">{t('encryption.usage')}</th>
                  <th>{t('encryption.created')}</th>
                </tr>
              </thead>
              <tbody>
                {deks.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <code>{row.id.slice(0, 8)}…</code>
                      {deks.active_dek_id === row.id && (
                        <span className="badge out"> {t('encryption.active')}</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge encryption-dek-${row.status}`}>
                        {dekStatusBadge(row.status, t)}
                      </span>
                    </td>
                    <td className="num">{formatInteger(row.usage_count)}</td>
                    <td className="stats-day">{fmtDate(row.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </AdminTableCard>
    </AdminPage>
  )
}
