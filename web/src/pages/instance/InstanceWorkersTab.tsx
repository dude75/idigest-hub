import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { AdminPage, AdminTableCard } from '../../components/AdminSection'
import { StatCard, StatGrid } from '../../components/StatCard'
import { WorkerHealthBadge, isWorkerHealthy, isWorkerUnhealthy } from '../../components/WorkerHealthBadge'
import type { Worker, WorkerEngineOption, WorkerProbeResult } from '../../types'
import { formatInteger, showError } from '../../util'
import { emptyWorker } from './constants'

const SELECTABLE_STATUSES = new Set(['loaded', 'unavailable'])

function selectableEngines(models: WorkerEngineOption[] | undefined) {
  return (models || []).filter((item) => SELECTABLE_STATUSES.has(item.status))
}

export function InstanceWorkersTab() {
  const { t } = useTranslation()
  const [workers, setWorkers] = useState<Worker[]>([])
  const [wform, setWform] = useState(emptyWorker)
  const [editW, setEditW] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [probing, setProbing] = useState(false)
  const [probe, setProbe] = useState<WorkerProbeResult | null>(null)
  const [probeOk, setProbeOk] = useState(false)

  async function load() {
    try {
      setWorkers((await api<{ items: Worker[] }>('/workers')).items)
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const summary = useMemo(() => ({
    total: workers.length,
    enabled: workers.filter((w) => w.enabled).length,
    healthy: workers.filter((w) => isWorkerHealthy(w)).length,
    unhealthy: workers.filter((w) => isWorkerUnhealthy(w)).length,
  }), [workers])

  const probeAsr = useMemo(() => selectableEngines(probe?.asr_models), [probe])
  const probeDiar = useMemo(() => selectableEngines(probe?.diarization_models), [probe])

  function toggleModel(kind: 'asr_models' | 'diarization_models', modelId: string) {
    setWform((prev) => {
      const current = prev[kind]
      const next = current.includes(modelId)
        ? current.filter((id) => id !== modelId)
        : [...current, modelId]
      return { ...prev, [kind]: next }
    })
  }

  async function probeWorker(opts?: { workerId?: string; baseUrl?: string; type?: string }) {
    const workerId = opts?.workerId ?? editW
    const baseUrl = (opts?.baseUrl ?? wform.base_url).trim()
    const workerType = opts?.type ?? wform.type
    if (!baseUrl) return
    if (!workerId && !wform.api_token.trim()) return
    setProbing(true)
    setProbeOk(false)
    try {
      const payload: Record<string, string> = {
        type: workerType,
        base_url: baseUrl,
      }
      if (wform.api_token.trim()) payload.api_token = wform.api_token.trim()
      if (workerId) payload.worker_id = workerId
      const result = await api<WorkerProbeResult>('/workers/probe', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setProbe(result)
      setProbeOk(true)
      if (wform.type === 'transcribe') {
        const asrIds = selectableEngines(result.asr_models).map((item) => item.id)
        const diarIds = selectableEngines(result.diarization_models).map((item) => item.id)
        setWform((prev) => ({
          ...prev,
          asr_models: prev.asr_models.filter((id) => asrIds.includes(id)),
          diarization_models: prev.diarization_models.filter((id) => diarIds.includes(id)),
        }))
      }
    } catch (e) {
      setProbe(null)
      showError(e)
    } finally {
      setProbing(false)
    }
  }

  async function saveWorker() {
    try {
      const body: Record<string, unknown> = {
        type: wform.type,
        name: wform.name,
        base_url: wform.base_url,
        weight: Number(wform.weight),
        enabled: wform.enabled,
      }
      if (wform.api_token.trim()) body.api_token = wform.api_token.trim()
      if (wform.type === 'transcribe') {
        body.asr_models = wform.asr_models
        body.diarization_models = wform.diarization_models
      }
      if (editW) {
        await api(`/workers/${editW}`, { method: 'PATCH', body: JSON.stringify(body) })
      } else {
        await api('/workers', { method: 'POST', body: JSON.stringify(body) })
      }
      setWform(emptyWorker)
      setEditW(null)
      setFormOpen(false)
      setProbe(null)
      setProbeOk(false)
      await load()
    } catch (e) {
      showError(e)
    }
  }

  function startEdit(w: Worker) {
    setEditW(w.id)
    setFormOpen(true)
    setProbe(null)
    setProbeOk(false)
    setWform({
      type: w.type,
      name: w.name,
      base_url: w.base_url,
      api_token: '',
      weight: w.weight,
      enabled: w.enabled,
      asr_models: w.asr_models || [],
      diarization_models: w.diarization_models || [],
    })
    if (w.type === 'transcribe') {
      void probeWorker({ workerId: w.id, baseUrl: w.base_url, type: w.type })
    }
  }

  function cancelEdit() {
    setEditW(null)
    setWform(emptyWorker)
    setFormOpen(false)
    setProbe(null)
    setProbeOk(false)
  }

  const canSaveTranscribe =
    wform.type !== 'transcribe' || (probeOk && wform.asr_models.length > 0 && probe !== null)
  const canProbe = Boolean(wform.base_url.trim() && (wform.api_token.trim() || editW))

  return (
    <AdminPage>
      <StatGrid>
        <StatCard label={t('instance.workersTotal')} value={formatInteger(summary.total)} tone="ops" />
        <StatCard label={t('instance.workersEnabled')} value={formatInteger(summary.enabled)} tone="audio" />
        <StatCard label={t('instance.workersHealthy')} value={formatInteger(summary.healthy)} tone="transcribe" />
        <StatCard label={t('instance.workersUnhealthy')} value={formatInteger(summary.unhealthy)} tone="amount" />
      </StatGrid>

      <details
        className="fold org-fold org-create-fold card"
        open={formOpen}
        onToggle={(e) => setFormOpen(e.currentTarget.open)}
      >
        <summary className="org-fold-summary">
          <span>{editW ? t('instance.workerEdit') : t('instance.workerCreate')}</span>
        </summary>
        <div className="stack fold-body">
        <label>{t('instance.type')}
          <select
            value={wform.type}
            onChange={(e) => {
              setWform({ ...wform, type: e.target.value })
              setProbe(null)
              setProbeOk(false)
            }}
          >
            <option value="transcribe">{t('instance.transcribe')}</option>
            <option value="summarize">{t('instance.summarize')}</option>
          </select>
        </label>
        <label>{t('common.name')}<input value={wform.name} onChange={(e) => setWform({ ...wform, name: e.target.value })} /></label>
        <label>{t('instance.baseUrl')}<input value={wform.base_url} onChange={(e) => { setWform({ ...wform, base_url: e.target.value }); setProbeOk(false) }} /></label>
        <label>{t('instance.apiToken')}<input value={wform.api_token} onChange={(e) => { setWform({ ...wform, api_token: e.target.value }); setProbeOk(false) }} placeholder={editW ? t('instance.apiTokenKeep') : ''} /></label>
        {wform.type === 'transcribe' ? (
          <>
            <button type="button" disabled={!canProbe || probing} onClick={() => void probeWorker()}>
              {probing ? t('instance.workerProbing') : t('instance.workerProbe')}
            </button>
            {probeOk ? <p className="ok">{t('instance.workerProbeOk')}</p> : null}
            {probe && wform.type === 'transcribe' ? (
              <div className="stack">
                <p className="muted">{t('instance.workerModelsHint')}</p>
                <fieldset className="stack">
                  <legend>{t('instance.asr')}</legend>
                  {probeAsr.length === 0 ? <p className="muted">{t('instance.workerModelsEmpty')}</p> : null}
                  {probeAsr.map((item) => (
                    <label className="row" key={item.id}>
                      <input
                        type="checkbox"
                        checked={wform.asr_models.includes(item.id)}
                        onChange={() => toggleModel('asr_models', item.id)}
                      />
                      <span className="grow">
                        <strong>{item.id}</strong>
                        <span className="muted"> — {item.status}</span>
                      </span>
                    </label>
                  ))}
                </fieldset>
                <fieldset className="stack">
                  <legend>{t('instance.diarization')}</legend>
                  {probeDiar.length === 0 ? <p className="muted">{t('instance.workerModelsEmpty')}</p> : null}
                  {probeDiar.map((item) => (
                    <label className="row" key={item.id}>
                      <input
                        type="checkbox"
                        checked={wform.diarization_models.includes(item.id)}
                        onChange={() => toggleModel('diarization_models', item.id)}
                      />
                      <span className="grow">
                        <strong>{item.id}</strong>
                        <span className="muted"> — {item.status}</span>
                      </span>
                    </label>
                  ))}
                </fieldset>
              </div>
            ) : null}
          </>
        ) : null}
        <label>{t('instance.weight')}<input type="number" min={1} value={wform.weight} onChange={(e) => setWform({ ...wform, weight: Number(e.target.value) })} /></label>
        <label className="row">
          <input type="checkbox" checked={wform.enabled} onChange={(e) => setWform({ ...wform, enabled: e.target.checked })} />
          {t('instance.enabled')}
        </label>
        <div className="row">
          <button className="primary" type="button" disabled={!canSaveTranscribe} onClick={() => void saveWorker()}>{editW ? t('common.save') : t('common.create')}</button>
          {editW ? <button type="button" onClick={cancelEdit}>{t('common.cancel')}</button> : null}
        </div>
        </div>
      </details>

      <AdminTableCard title={t('instance.workersList')} empty={t('common.empty')} isEmpty={workers.length === 0}>
        {workers.length > 0 ? (
          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>{t('common.name')}</th>
                  <th>{t('instance.type')}</th>
                  <th>{t('instance.workerModels')}</th>
                  <th>{t('instance.weight')}</th>
                  <th>{t('instance.enabled')}</th>
                  <th>{t('instance.health')}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {workers.map((w) => (
                  <tr key={w.id}>
                    <td>{w.name || w.base_url}</td>
                    <td>{t(`task.type.${w.type}`, { defaultValue: w.type })}</td>
                    <td>
                      {w.type === 'transcribe'
                        ? [
                            ...(w.asr_models || []).map((id) => `ASR:${id}`),
                            ...(w.diarization_models || []).map((id) => `D:${id}`),
                          ].join(', ') || '—'
                        : '—'}
                    </td>
                    <td className="num">{formatInteger(w.weight)}</td>
                    <td>{w.enabled ? t('common.yes') : t('common.no')}</td>
                    <td><WorkerHealthBadge worker={w} /></td>
                    <td className="table-actions">
                      <div className="row">
                        <button type="button" onClick={() => startEdit(w)}>{t('common.edit')}</button>
                        <button type="button" className="danger" onClick={() => void api(`/workers/${w.id}`, { method: 'DELETE' }).then(load)}>{t('common.delete')}</button>
                      </div>
                    </td>
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
