import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import type { SchemaWorkerListResponse } from '../../openapi'
import { AdminFormCard, AdminPage, AdminTableCard } from '../../components/AdminSection'
import { AdminFormActions, AppSubmitButton } from '../../components/app/AdminUi'
import { jsonDirty } from '../../util/formDirty'
import {
  AdminDataTable,
  AdminTableHeadHint,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  adminTableCellActions,
  adminTableCellMuted,
  adminTableCellNum,
  adminTableCellPrimary,
  adminTableHeadActions,
  adminTableHeadNum,
} from '../../components/app/AdminDataTable'
import { StatCard, StatGrid } from '../../components/StatCard'
import { WorkerHealthBadge, isWorkerHealthy, isWorkerUnhealthy } from '../../components/WorkerHealthBadge'
import type { Worker, WorkerEngineOption, WorkerProbeResult, WorkersListSummary } from '../../types'
import { formatInteger, showError } from '../../util'
import { emptyWorker } from './constants'
import { normalizeCaptureCapacitySummary, typeHubWorkerCapacity, workerCapacityCell } from './workerCapacity'
import { WorkerImpactModal } from './WorkerImpactModal'
import { Button } from '@/components/ui/button'
import { AdminRowActions } from '../../components/app/AdminUi'
import { AppCheckboxRow, AppInputField, AppSelectField } from '../../components/app/AppFormControls'

const LOADED_CONNECTOR_STATUS = 'loaded'

function selectableEngines(models: WorkerEngineOption[] | undefined) {
  return (models || []).filter((item) => item.status === LOADED_CONNECTOR_STATUS || item.status === 'unavailable')
}

function loadedCaptureConnectors(models: WorkerEngineOption[] | undefined) {
  return (models || []).filter((item) => item.status === LOADED_CONNECTOR_STATUS)
}

export function InstanceWorkersTab() {
  const { t } = useTranslation()
  const [workers, setWorkers] = useState<Worker[]>([])
  const [workersSummary, setWorkersSummary] = useState<WorkersListSummary | null>(null)
  const [wform, setWform] = useState(emptyWorker)
  const [editW, setEditW] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [probing, setProbing] = useState(false)
  const [probe, setProbe] = useState<WorkerProbeResult | null>(null)
  const [probeOk, setProbeOk] = useState(false)
  const formRef = useRef<HTMLDivElement>(null)
  const [impactModal, setImpactModal] = useState<{
    mode: 'delete' | 'change'
    worker: Worker
    changeBody?: Record<string, unknown>
  } | null>(null)

  async function load(opts?: { probe?: boolean; refresh?: boolean }) {
    const probe = opts?.probe ?? true
    const refresh = opts?.refresh ?? false
    const qs = new URLSearchParams()
    if (!probe) qs.set('probe', 'false')
    if (refresh) qs.set('refresh', 'true')
    const path = qs.size ? `/workers?${qs.toString()}` : '/workers'
    try {
      const result = await api<SchemaWorkerListResponse>(path)
      setWorkers(result.items)
      setWorkersSummary(result.summary)
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    void (async () => {
      await load({ probe: false })
      await load({ probe: true, refresh: true })
    })()
  }, [])

  const summary = useMemo(() => ({
    total: workersSummary?.total ?? workers.length,
    enabled: workersSummary?.enabled ?? workers.filter((w) => w.enabled).length,
    available: workersSummary?.available ?? 0,
    healthy: workers.filter((w) => isWorkerHealthy(w)).length,
    unhealthy: workers.filter((w) => isWorkerUnhealthy(w)).length,
    byType: workersSummary?.by_type,
    hubLimits: workersSummary?.hub_limits,
    captureCapacity: normalizeCaptureCapacitySummary(workersSummary, workers),
  }), [workers, workersSummary])

  const hasCaptureWorkers = workers.some((w) => w.type === 'capture')
  const transcribeHubCapacity = useMemo(() => typeHubWorkerCapacity(workers, 'transcribe'), [workers])
  const summarizeHubCapacity = useMemo(() => typeHubWorkerCapacity(workers, 'summarize'), [workers])

  const availableDetailTitle = useMemo(() => {
    const lines: string[] = []
    if (transcribeHubCapacity) {
      lines.push(
        `${t('task.type.transcribe')}: ${formatInteger(transcribeHubCapacity.available)} / ${formatInteger(transcribeHubCapacity.max)}`,
      )
    }
    if (summarizeHubCapacity) {
      lines.push(
        `${t('task.type.summarize')}: ${formatInteger(summarizeHubCapacity.available)} / ${formatInteger(summarizeHubCapacity.max)}`,
      )
    }
    if (summary.byType?.capture) {
      lines.push(
        `${t('task.type.capture')}: ${formatInteger(summary.byType.capture.available)} / ${formatInteger(summary.byType.capture.total)}`,
      )
    }
    if (summary.hubLimits) {
      lines.push(
        t('instance.workersHubImportLimit', { count: formatInteger(summary.hubLimits.import_max_concurrent) }),
      )
    }
    if (summary.captureCapacity && summary.captureCapacity.max > 0) {
      lines.push(
        t('instance.workersCaptureCapacity', {
          available: formatInteger(summary.captureCapacity.available),
          max: formatInteger(summary.captureCapacity.max),
        }),
      )
    }
    return lines.length ? lines.join('\n') : undefined
  }, [summary.byType, summary.hubLimits, summary.captureCapacity, summarizeHubCapacity, transcribeHubCapacity, t])

  const probeAsr = useMemo(() => selectableEngines(probe?.asr_models), [probe])
  const probeDiar = useMemo(() => selectableEngines(probe?.diarization_models), [probe])

  function toggleCaptureConnector(connectorId: string) {
    const status = probe?.connectors?.find((item) => item.id === connectorId)?.status
    if (status !== LOADED_CONNECTOR_STATUS) return
    setWform((prev) => {
      const current = prev.capture_connectors
      const next = current.includes(connectorId)
        ? current.filter((id) => id !== connectorId)
        : [...current, connectorId]
      return { ...prev, capture_connectors: next }
    })
  }

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
      if (wform.type === 'capture') {
        const loadedIds = loadedCaptureConnectors(result.connectors).map((item) => item.id)
        setWform((prev) => {
          const kept = prev.capture_connectors.filter((id) => loadedIds.includes(id))
          return {
            ...prev,
            capture_connectors: kept.length > 0 ? kept : loadedIds,
          }
        })
      }
    } catch (e) {
      setProbe(null)
      showError(e)
    } finally {
      setProbing(false)
    }
  }

  function buildWorkerBody(): Record<string, unknown> {
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
    if (wform.type === 'capture') {
      body.capture_connectors = wform.capture_connectors
    }
    return body
  }

  async function saveWorkerDirect(body: Record<string, unknown>, workerId: string | null) {
    if (workerId) {
      await api(`/workers/${workerId}`, { method: 'PATCH', body: JSON.stringify(body) })
    } else {
      await api('/workers', { method: 'POST', body: JSON.stringify(body) })
    }
    setWform(emptyWorker)
    setEditW(null)
    setFormOpen(false)
    setProbe(null)
    setProbeOk(false)
    await load()
  }

  function requestSaveWorker() {
    const body = buildWorkerBody()
    if (editW) {
      const worker = workers.find((item) => item.id === editW)
      if (!worker) return
      setImpactModal({ mode: 'change', worker, changeBody: body })
      return
    }
    void saveWorkerDirect(body, null).catch(showError)
  }

  function scrollToForm() {
    requestAnimationFrame(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  function openCreate() {
    setEditW(null)
    setWform(emptyWorker)
    setProbe(null)
    setProbeOk(false)
    setFormOpen(true)
    scrollToForm()
  }

  function startEdit(w: Worker) {
    setEditW(w.id)
    setFormOpen(true)
    scrollToForm()
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
      capture_connectors: w.capture_connectors || [],
    })
    if (w.type === 'transcribe' || w.type === 'capture' || w.type === 'summarize') {
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

  const workerBaseline = useMemo(() => {
    if (!editW) return emptyWorker
    const w = workers.find((x) => x.id === editW)
    if (!w) return emptyWorker
    return {
      type: w.type,
      name: w.name,
      base_url: w.base_url,
      api_token: '',
      weight: w.weight,
      enabled: w.enabled,
      asr_models: w.asr_models || [],
      diarization_models: w.diarization_models || [],
      capture_connectors: w.capture_connectors || [],
    }
  }, [editW, workers])

  const workerDirty = jsonDirty(wform, workerBaseline)

  const canSaveWorker =
    (wform.type !== 'transcribe' || (probeOk && wform.asr_models.length > 0 && probe !== null)) &&
    (wform.type !== 'capture' || (probeOk && wform.capture_connectors.length > 0 && probe !== null))

  const workerReady = canSaveWorker && workerDirty
  const canProbe = Boolean(wform.base_url.trim() && (wform.api_token.trim() || editW))
  const allProbeConnectors = useMemo(() => probe?.connectors ?? [], [probe])

  return (
    <AdminPage>
      <StatGrid>
        <StatCard label={t('instance.workersTotal')} value={formatInteger(summary.total)} tone="ops" />
        <StatCard label={t('instance.workersEnabled')} value={formatInteger(summary.enabled)} tone="audio" />
        <StatCard
          label={t('instance.workersAvailable')}
          value={formatInteger(summary.available)}
          unit={
            summary.enabled > 0
              ? t('instance.workersAvailableOfEnabled', { enabled: formatInteger(summary.enabled) })
              : undefined
          }
          title={availableDetailTitle}
          tone="transcribe"
        />
        <StatCard label={t('instance.workersHealthy')} value={formatInteger(summary.healthy)} tone="summarize" />
        <StatCard label={t('instance.workersUnhealthy')} value={formatInteger(summary.unhealthy)} tone="amount" />
        {hasCaptureWorkers ? (
          summary.captureCapacity ? (
            <StatCard
              label={t('instance.workersCaptureCapacityLabel')}
              value={formatInteger(summary.captureCapacity.available)}
              unit={t('instance.workersCaptureCapacityOfMax', {
                max: formatInteger(summary.captureCapacity.max),
              })}
              title={t('instance.workersCaptureCapacityHint')}
              tone="ops"
            />
          ) : (
            <StatCard
              label={t('instance.workersCaptureCapacityLabel')}
              value="—"
              unit={t('instance.workerCapacityUnknown')}
              title={t('instance.workersCaptureCapacityHint')}
              tone="ops"
            />
          )
        ) : null}
      </StatGrid>

      {formOpen ? (
        <div ref={formRef}>
          <AdminFormCard title={editW ? t('instance.workerEdit') : t('instance.workerCreate')}>
        <AppSelectField
          label={t('instance.type')}
          htmlFor="worker-type"
          value={wform.type}
          onValueChange={(type) => {
            setWform({ ...wform, type })
            setProbe(null)
            setProbeOk(false)
          }}
          options={[
            { value: 'transcribe', label: t('instance.transcribe') },
            { value: 'summarize', label: t('instance.summarize') },
            { value: 'capture', label: t('instance.capture') },
          ]}
        />
        <AppInputField label={t('common.name')} htmlFor="worker-name" value={wform.name} onChange={(e) => setWform({ ...wform, name: e.target.value })} />
        <AppInputField label={t('instance.baseUrl')} htmlFor="worker-base-url" value={wform.base_url} onChange={(e) => { setWform({ ...wform, base_url: e.target.value }); setProbeOk(false) }} />
        <AppInputField label={t('instance.apiToken')} htmlFor="worker-api-token" value={wform.api_token} onChange={(e) => { setWform({ ...wform, api_token: e.target.value }); setProbeOk(false) }} placeholder={editW ? t('instance.apiTokenKeep') : ''} />
        {wform.type === 'transcribe' ? (
          <>
            <Button type="button" disabled={!canProbe || probing} onClick={() => void probeWorker()}>
              {probing ? t('instance.workerProbing') : t('instance.workerProbe')}
            </Button>
            {probeOk ? <p className="ok">{t('instance.workerProbeOk')}</p> : null}
            {probe && wform.type === 'transcribe' ? (
              <div className="flex flex-col gap-3">
                <p className="muted">{t('instance.workerModelsHint')}</p>
                <fieldset className="flex flex-col gap-3">
                  <legend>{t('instance.asr')}</legend>
                  {probeAsr.length === 0 ? <p className="muted">{t('instance.workerModelsEmpty')}</p> : null}
                  {probeAsr.map((item) => (
                    <AppCheckboxRow
                      key={item.id}
                      id={`worker-asr-${item.id}`}
                      className="items-start"
                      label={
                        <span className="grow">
                          <strong>{item.id}</strong>
                          <span className="muted"> — {item.status}</span>
                        </span>
                      }
                      checked={wform.asr_models.includes(item.id)}
                      onCheckedChange={() => toggleModel('asr_models', item.id)}
                    />
                  ))}
                </fieldset>
                <fieldset className="flex flex-col gap-3">
                  <legend>{t('instance.diarization')}</legend>
                  {probeDiar.length === 0 ? <p className="muted">{t('instance.workerModelsEmpty')}</p> : null}
                  {probeDiar.map((item) => (
                    <AppCheckboxRow
                      key={item.id}
                      id={`worker-diar-${item.id}`}
                      className="items-start"
                      label={
                        <span className="grow">
                          <strong>{item.id}</strong>
                          <span className="muted"> — {item.status}</span>
                        </span>
                      }
                      checked={wform.diarization_models.includes(item.id)}
                      onCheckedChange={() => toggleModel('diarization_models', item.id)}
                    />
                  ))}
                </fieldset>
              </div>
            ) : null}
          </>
        ) : null}
        {wform.type === 'summarize' ? (
          <>
            <Button type="button" disabled={!canProbe || probing} onClick={() => void probeWorker()}>
              {probing ? t('instance.workerProbing') : t('instance.workerProbe')}
            </Button>
            {probeOk ? <p className="ok">{t('instance.workerProbeOk')}</p> : null}
            {probe?.summarize_model ? (
              <p className="muted">
                {t('instance.summarizeModelLabel')}: <strong>{probe.summarize_model}</strong>
              </p>
            ) : null}
          </>
        ) : null}
        {wform.type === 'capture' ? (
          <>
            <Button type="button" disabled={!canProbe || probing} onClick={() => void probeWorker()}>
              {probing ? t('instance.workerProbing') : t('instance.workerProbe')}
            </Button>
            {probeOk ? <p className="ok">{t('instance.workerProbeOk')}</p> : null}
            {probe && wform.type === 'capture' ? (
              <div className="flex flex-col gap-3">
                <p className="muted">{t('instance.captureConnectorsHint')}</p>
                <fieldset className="flex flex-col gap-3">
                  <legend>{t('instance.captureConnectors')}</legend>
                  {allProbeConnectors.length === 0 ? <p className="muted">{t('instance.workerModelsEmpty')}</p> : null}
                  {allProbeConnectors.map((item) => {
                    const selectable = item.status === LOADED_CONNECTOR_STATUS
                    return (
                      <AppCheckboxRow
                        key={item.id}
                        id={`worker-capture-${item.id}`}
                        className="items-start"
                        label={
                          <span className="grow">
                            <strong>{item.label?.trim() || item.id}</strong>
                            <span className="muted"> — {item.status}</span>
                          </span>
                        }
                        checked={wform.capture_connectors.includes(item.id)}
                        disabled={!selectable}
                        onCheckedChange={() => toggleCaptureConnector(item.id)}
                      />
                    )
                  })}
                </fieldset>
              </div>
            ) : null}
          </>
        ) : null}
        <AppInputField label={t('instance.weight')} htmlFor="worker-weight" type="number" min={1} value={wform.weight} onChange={(e) => setWform({ ...wform, weight: Number(e.target.value) })} />
        <AppCheckboxRow id="worker-enabled" label={t('instance.enabled')} checked={wform.enabled} onCheckedChange={(checked) => setWform({ ...wform, enabled: checked })} />
        <AdminFormActions>
          <AppSubmitButton ready={workerReady} onClick={() => requestSaveWorker()}>
            {editW ? t('common.save') : t('common.create')}
          </AppSubmitButton>
          <Button type="button" variant="outline" onClick={cancelEdit}>
            {t('common.cancel')}
          </Button>
        </AdminFormActions>
          </AdminFormCard>
        </div>
      ) : null}

      <AdminTableCard
        title={t('instance.workersList')}
        empty={t('common.empty')}
        isEmpty={workers.length === 0}
        tableLayout
        actions={
          <Button type="button" size="sm" onClick={openCreate}>
            {t('instance.workerCreate')}
          </Button>
        }
      >
        {workers.length > 0 ? (
          <AdminDataTable>
            <TableHeader>
              <TableRow>
                <TableHead>{t('common.name')}</TableHead>
                <TableHead>{t('instance.type')}</TableHead>
                <TableHead>{t('instance.workerModels')}</TableHead>
                <TableHead className={adminTableHeadNum}>{t('instance.weight')}</TableHead>
                <TableHead>{t('instance.enabled')}</TableHead>
                <TableHead>{t('instance.health')}</TableHead>
                <AdminTableHeadHint className={adminTableHeadNum} hint={t('instance.workerCapacityColumnHint')}>
                  {t('instance.workerCapacityColumn')}
                </AdminTableHeadHint>
                <TableHead className={adminTableHeadActions} />
              </TableRow>
            </TableHeader>
            <TableBody>
              {workers.map((w) => (
                <TableRow key={w.id}>
                  <TableCell className={adminTableCellPrimary}>{w.name || w.base_url}</TableCell>
                  <TableCell>{t(`task.type.${w.type}`, { defaultValue: w.type })}</TableCell>
                  <TableCell className={adminTableCellMuted}>
                    {w.type === 'transcribe'
                      ? [
                          ...(w.asr_models || []).map((id) => `ASR:${id}`),
                          ...(w.diarization_models || []).map((id) => `D:${id}`),
                        ].join(', ') || '—'
                      : w.type === 'capture'
                        ? (w.capture_connectors || []).join(', ') || '—'
                        : w.type === 'summarize'
                          ? w.summarize_model?.trim() || '—'
                          : '—'}
                  </TableCell>
                  <TableCell className={adminTableCellNum}>{formatInteger(w.weight)}</TableCell>
                  <TableCell>{w.enabled ? t('common.yes') : t('common.no')}</TableCell>
                  <TableCell>
                    <WorkerHealthBadge worker={w} />
                  </TableCell>
                  <TableCell className={adminTableCellNum}>
                    {(() => {
                      const cell = workerCapacityCell(w, workers)
                      if (!cell) return '—'
                      return `${formatInteger(cell.available)} / ${formatInteger(cell.max)}`
                    })()}
                  </TableCell>
                  <TableCell className={adminTableCellActions}>
                    <AdminRowActions>
                      <Button type="button" size="sm" variant="outline" onClick={() => startEdit(w)}>
                        {t('common.edit')}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="destructive"
                        onClick={() => setImpactModal({ mode: 'delete', worker: w })}
                      >
                        {t('common.delete')}
                      </Button>
                    </AdminRowActions>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </AdminDataTable>
        ) : null}
      </AdminTableCard>

      {impactModal ? (
        <WorkerImpactModal
          mode={impactModal.mode}
          worker={impactModal.worker}
          changeBody={impactModal.changeBody}
          onClose={() => setImpactModal(null)}
          onConfirm={async ({ remediation } = {}) => {
            if (impactModal.mode === 'delete') {
              await api(`/workers/${impactModal.worker.id}`, {
                method: 'DELETE',
                body: remediation ? JSON.stringify({ remediation }) : undefined,
              })
              await load()
              return
            }
            const body = {
              ...(impactModal.changeBody ?? buildWorkerBody()),
              ...(remediation ? { remediation } : {}),
            }
            await saveWorkerDirect(body, impactModal.worker.id)
          }}
        />
      ) : null}
    </AdminPage>
  )
}
