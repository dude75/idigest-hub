import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import type { DataEncryptionKey, EncryptionJob } from '../../types'
import { fmtDate, showError } from '../../util'

type DekList = {
  active_dek_id: string | null
  items: DataEncryptionKey[]
  running_job_id: string | null
  deks_pending_rewrap: number
  hub_secret_prev_configured: boolean
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
    if (!tables) return j.status
    const parts = Object.entries(tables)
      .filter(([, v]) => (v.total ?? 0) > 0 || (v.done ?? 0) > 0)
      .map(([k, v]) => `${k}: ${v.done ?? 0}/${v.total ?? 0}`)
    return parts.length ? parts.join(' · ') : j.status
  }

  return (
    <div className="stack">
      <div className="card stack">
        <p>{t('encryption.lead')}</p>
        {deks && deks.hub_secret_prev_configured && (
          <p className="hint">{t('encryption.hubSecretPrevHint')}</p>
        )}
        {deks && deks.deks_pending_rewrap > 0 && (
          <p className="error">{t('encryption.rewrapPending', { count: deks.deks_pending_rewrap })}</p>
        )}
        <div className="row wrap">
          <button type="button" disabled={busy || jobRunning} onClick={addDek}>
            {t('encryption.addDek')}
          </button>
          <button type="button" disabled={busy || jobRunning || !retiring} onClick={startReencrypt}>
            {t('encryption.reencrypt')}
          </button>
        </div>
      </div>

      {job && (
        <div className="card stack">
          <h2>{t('encryption.jobTitle')}</h2>
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
            <strong>{job.status}</strong> — {progressLabel(job)}
          </p>
          {job.error && <p className="error">{job.error}</p>}
          {jobRunning && (
            <button type="button" disabled={busy} onClick={cancelJob}>
              {t('encryption.cancel')}
            </button>
          )}
        </div>
      )}

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t('encryption.dekId')}</th>
              <th>{t('encryption.status')}</th>
              <th>{t('encryption.usage')}</th>
              <th>{t('encryption.created')}</th>
            </tr>
          </thead>
          <tbody>
            {(deks?.items ?? []).map((row) => (
              <tr key={row.id}>
                <td>
                  <code>{row.id.slice(0, 8)}…</code>
                  {deks?.active_dek_id === row.id && ` (${t('encryption.active')})`}
                </td>
                <td>{row.status}</td>
                <td>{row.usage_count}</td>
                <td>{fmtDate(row.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!deks?.items.length && <p>{t('encryption.noDeks')}</p>}
      </div>
    </div>
  )
}
