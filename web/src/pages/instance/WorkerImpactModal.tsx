import { Children, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { Modal } from '../../components/Modal'
import type {
  CaptureWorkerChoice,
  DispatchablePair,
  SummarizeModelChoice,
  Worker,
  WorkerDeleteImpact,
  WorkerDeleteImpactTask,
  WorkerRemediationPayload,
} from '../../types'
import { formatInteger, showError, truncateLabel } from '../../util'

type Props = {
  mode: 'delete' | 'change'
  worker: Worker
  changeBody?: Record<string, unknown>
  onClose: () => void
  onConfirm: (opts?: { remediation?: WorkerRemediationPayload }) => void | Promise<void>
}

function pairKey(pair: DispatchablePair) {
  return `${pair.asr_model}\0${pair.diarization_model ?? ''}`
}

function formatPairLabel(
  pair: DispatchablePair,
  t: (key: string, opts?: Record<string, unknown>) => string,
) {
  return t('instance.workerImpactModelPair', {
    asr: pair.asr_model,
    diarization: pair.diarization_model || t('instance.diarizationOff'),
  })
}

function formatCaptureWorkerLabel(worker: CaptureWorkerChoice) {
  return worker.name.trim() || worker.base_url
}

type ModelPair = { asr: string; diarization: string | null }

type UnavailableItem =
  | { kind: 'pair'; pair: ModelPair; users: number; tasks: number }
  | { kind: 'defaults'; pair: ModelPair }
  | { kind: 'summarize_model'; model: string; users: number; tasks: number }
  | { kind: 'summarize_defaults'; model: string | null }
  | { kind: 'last_transcribe' }
  | { kind: 'last_summarize' }
  | { kind: 'summarize_remaining'; count: number }
  | { kind: 'capture_losing_jitsi' }

type InUseItem =
  | { kind: 'user'; email: string; pair: ModelPair }
  | { kind: 'summarize_user'; email: string; model: string | null }
  | { kind: 'tasks'; pair: ModelPair; queued: number; running: number; total: number }
  | { kind: 'defaults'; pair: ModelPair }
  | { kind: 'summarize_defaults'; model: string | null }
  | { kind: 'summarize_tasks'; queued: number; running: number; total: number }
  | { kind: 'capture_host'; host: string; orgName: string }
  | { kind: 'capture_tasks'; total: number }

function matchesPair(asr: string, diarization: string | null | undefined, pair: DispatchablePair) {
  return pair.asr_model === asr && (pair.diarization_model ?? null) === (diarization ?? null)
}

function useImpactSections(
  impact: WorkerDeleteImpact | null,
  workerType: string,
): { unavailable: UnavailableItem[]; inUse: InUseItem[] } {
  return useMemo(() => {
    if (!impact) return { unavailable: [], inUse: [] }

    const users = impact.affected_users ?? []
    const tasks = impact.affected_tasks ?? []
    const unavailable: UnavailableItem[] = []
    const inUse: InUseItem[] = []

    if (workerType === 'capture') {
      if (impact.capture_losing_jitsi) {
        unavailable.push({ kind: 'capture_losing_jitsi' })
      }
      for (const row of impact.capture_jitsi_hosts ?? []) {
        inUse.push({ kind: 'capture_host', host: row.host, orgName: row.org_name })
      }
      const captureTasks = impact.capture_tasks_count ?? 0
      if (captureTasks > 0) {
        inUse.push({ kind: 'capture_tasks', total: captureTasks })
      }
      return { unavailable, inUse }
    }

    if (workerType === 'transcribe') {
      for (const pair of impact.lost_model_pairs ?? []) {
        const pairUsers = users.filter((user) => matchesPair(user.asr_model ?? 'whisper', user.diarization_model, pair))
        const pairTasks = tasks.filter((task) => matchesPair(task.asr_model ?? 'whisper', task.diarization_model, pair))
        unavailable.push({
          kind: 'pair',
          pair: { asr: pair.asr_model, diarization: pair.diarization_model ?? null },
          users: pairUsers.length,
          tasks: pairTasks.length,
        })
      }

      if (impact.instance_defaults_broken && impact.instance_defaults?.asr_model) {
        const pair = {
          asr: impact.instance_defaults.asr_model,
          diarization: impact.instance_defaults.diarization_model ?? null,
        }
        unavailable.push({ kind: 'defaults', pair })
        inUse.push({ kind: 'defaults', pair })
      }

      if ((impact.remaining_transcribe_workers ?? 0) === 0 && (impact.lost_model_pairs?.length ?? 0) > 0) {
        unavailable.push({ kind: 'last_transcribe' })
      }
    } else if (workerType === 'summarize') {
      for (const model of impact.lost_summarize_models ?? []) {
        const modelUsers = users.filter((user) => user.summarize_model === model)
        const modelTasks = tasks.filter((task) => task.summarize_model === model)
        unavailable.push({
          kind: 'summarize_model',
          model,
          users: modelUsers.length,
          tasks: modelTasks.length,
        })
      }
      if (impact.instance_defaults_broken && impact.instance_defaults?.summarize_model) {
        const model = impact.instance_defaults.summarize_model
        unavailable.push({ kind: 'summarize_defaults', model })
        inUse.push({ kind: 'summarize_defaults', model })
      }
      if (impact.last_enabled_worker) unavailable.push({ kind: 'last_summarize' })
      unavailable.push({ kind: 'summarize_remaining', count: impact.remaining_summarize_workers ?? 0 })
    }

    for (const user of users) {
      if (workerType === 'summarize') {
        inUse.push({
          kind: 'summarize_user',
          email: user.email,
          model: user.summarize_model ?? null,
        })
      } else {
        inUse.push({
          kind: 'user',
          email: user.email,
          pair: { asr: user.asr_model ?? '', diarization: user.diarization_model ?? null },
        })
      }
    }

    if (workerType === 'transcribe') {
      const tasksByPair = new Map<string, WorkerDeleteImpactTask[]>()
      for (const task of tasks) {
        const key = `${task.asr_model ?? 'whisper'}\0${task.diarization_model ?? ''}`
        const bucket = tasksByPair.get(key) ?? []
        bucket.push(task)
        tasksByPair.set(key, bucket)
      }
      for (const [, group] of tasksByPair) {
        const sample = group[0]
        inUse.push({
          kind: 'tasks',
          pair: { asr: sample.asr_model ?? 'whisper', diarization: sample.diarization_model ?? null },
          queued: group.filter((task) => task.status === 'queued').length,
          running: group.filter((task) => task.status === 'running').length,
          total: group.length,
        })
      }
    } else if (workerType === 'summarize' && tasks.length > 0) {
      inUse.push({
        kind: 'summarize_tasks',
        queued: tasks.filter((task) => task.status === 'queued').length,
        running: tasks.filter((task) => task.status === 'running').length,
        total: tasks.length,
      })
    }

    return { unavailable, inUse }
  }, [impact, workerType])
}

function ModelPairChip({
  pair,
  t,
}: {
  pair: ModelPair
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  return (
    <code className="worker-impact-pair">
      {t('instance.workerImpactModelPair', {
        asr: pair.asr,
        diarization: pair.diarization || t('instance.diarizationOff'),
      })}
    </code>
  )
}

function UsageCounts({
  users,
  tasks,
  t,
}: {
  users: number
  tasks: number
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  if (users === 0 && tasks === 0) {
    return <span className="worker-impact-tag idle">{t('instance.workerImpactIdle')}</span>
  }
  return (
    <span className="worker-impact-counts">
      {users > 0 ? (
        <span className="worker-impact-tag">{t('instance.workerImpactUsersTag', { count: users })}</span>
      ) : null}
      {tasks > 0 ? (
        <span className="worker-impact-tag">{t('instance.workerImpactTasksTag', { count: tasks })}</span>
      ) : null}
    </span>
  )
}

function UnavailableRow({
  item,
  t,
}: {
  item: UnavailableItem
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  if (item.kind === 'pair') {
    return (
      <li className="worker-impact-row">
        <ModelPairChip pair={item.pair} t={t} />
        <UsageCounts users={item.users} tasks={item.tasks} t={t} />
      </li>
    )
  }
  if (item.kind === 'defaults') {
    return (
      <li className="worker-impact-row">
        <span className="worker-impact-label">{t('instance.workerImpactDefaultsLabel')}</span>
        <ModelPairChip pair={item.pair} t={t} />
      </li>
    )
  }
  if (item.kind === 'summarize_model') {
    return (
      <li className="worker-impact-row">
        <code className="worker-impact-pair">{item.model}</code>
        <UsageCounts users={item.users} tasks={item.tasks} t={t} />
      </li>
    )
  }
  if (item.kind === 'summarize_defaults') {
    return (
      <li className="worker-impact-row">
        <span className="worker-impact-label">{t('instance.workerImpactDefaultsLabel')}</span>
        <code className="worker-impact-pair">{item.model || '—'}</code>
      </li>
    )
  }
  if (item.kind === 'last_transcribe') {
    return <li className="worker-impact-row worker-impact-note">{t('instance.workerImpactLastTranscribeWorker')}</li>
  }
  if (item.kind === 'last_summarize') {
    return <li className="worker-impact-row worker-impact-note warn">{t('instance.workerImpactLastSummarizeWorker')}</li>
  }
  if (item.kind === 'capture_losing_jitsi') {
    return <li className="worker-impact-row worker-impact-note warn">{t('instance.workerImpactCaptureLosingJitsi')}</li>
  }
  return (
    <li className="worker-impact-row worker-impact-note muted">
      {t('instance.workerImpactSummarizeRemaining', { count: formatInteger(item.count) })}
    </li>
  )
}

function InUseRow({
  item,
  t,
}: {
  item: InUseItem
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  if (item.kind === 'user') {
    return (
      <li className="worker-impact-row">
        <span className="worker-impact-email">{item.email}</span>
        <ModelPairChip pair={item.pair} t={t} />
      </li>
    )
  }
  if (item.kind === 'summarize_user') {
    return (
      <li className="worker-impact-row">
        <span className="worker-impact-email">{item.email}</span>
        <code className="worker-impact-pair">{item.model || '—'}</code>
      </li>
    )
  }
  if (item.kind === 'defaults') {
    return (
      <li className="worker-impact-row">
        <span className="worker-impact-label">{t('instance.workerImpactDefaultsLabel')}</span>
        <ModelPairChip pair={item.pair} t={t} />
      </li>
    )
  }
  if (item.kind === 'summarize_defaults') {
    return (
      <li className="worker-impact-row">
        <span className="worker-impact-label">{t('instance.workerImpactDefaultsLabel')}</span>
        <code className="worker-impact-pair">{item.model || '—'}</code>
      </li>
    )
  }
  if (item.kind === 'capture_host') {
    const full = `${item.orgName} · ${item.host}`
    return (
      <li className="worker-impact-row">
        <span className="worker-impact-capture-map" title={full}>
          <span className="worker-impact-org-name">{truncateLabel(item.orgName, 24)}</span>
          <span className="muted worker-impact-capture-sep"> · </span>
          <code className="worker-impact-pair">{item.host}</code>
        </span>
      </li>
    )
  }
  if (item.kind === 'capture_tasks') {
    return (
      <li className="worker-impact-row worker-impact-note">
        {t('instance.workerImpactCaptureTasks', { count: formatInteger(item.total) })}
      </li>
    )
  }
  if (item.kind === 'summarize_tasks') {
    return (
      <li className="worker-impact-row">
        <span className="worker-impact-label">{t('instance.summarize')}</span>
        <span className="worker-impact-counts">
          <span className="worker-impact-tag">{t('instance.workerImpactTasksTag', { count: item.total })}</span>
          {item.queued > 0 ? (
            <span className="worker-impact-tag subtle">{t('instance.workerImpactQueuedTag', { count: item.queued })}</span>
          ) : null}
          {item.running > 0 ? (
            <span className="worker-impact-tag subtle">{t('instance.workerImpactRunningTag', { count: item.running })}</span>
          ) : null}
        </span>
      </li>
    )
  }
  return (
    <li className="worker-impact-row">
      <ModelPairChip pair={item.pair} t={t} />
      <span className="worker-impact-counts">
        <span className="worker-impact-tag">{t('instance.workerImpactTasksTag', { count: item.total })}</span>
        {item.queued > 0 ? (
          <span className="worker-impact-tag subtle">{t('instance.workerImpactQueuedTag', { count: item.queued })}</span>
        ) : null}
        {item.running > 0 ? (
          <span className="worker-impact-tag subtle">{t('instance.workerImpactRunningTag', { count: item.running })}</span>
        ) : null}
      </span>
    </li>
  )
}

function ImpactSection({
  title,
  hint,
  empty,
  children,
}: {
  title: string
  hint?: string
  empty?: string
  children: ReactNode
}) {
  const hasContent = Children.count(children) > 0
  return (
    <section className="worker-impact-section">
      <div className="worker-impact-section-head">
        <h3>{title}</h3>
        {hint ? <p className="muted worker-impact-section-hint">{hint}</p> : null}
      </div>
      {hasContent ? (
        <ul className="worker-impact-list">{children}</ul>
      ) : empty ? (
        <p className="muted worker-impact-empty">{empty}</p>
      ) : null}
    </section>
  )
}

export function WorkerImpactModal({ mode, worker, changeBody, onClose, onConfirm }: Props) {
  const { t } = useTranslation()
  const [impact, setImpact] = useState<WorkerDeleteImpact | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [applyRemediation, setApplyRemediation] = useState(true)
  const [selectedPairKey, setSelectedPairKey] = useState('')
  const [selectedSummarizeModel, setSelectedSummarizeModel] = useState('')
  const [selectedCaptureWorkerId, setSelectedCaptureWorkerId] = useState('')
  const workerType = changeBody?.type != null ? String(changeBody.type) : worker.type
  const workerLabel = worker.name || worker.base_url
  const { unavailable, inUse } = useImpactSections(impact, workerType)
  const selectedPair = useMemo(() => {
    const pairs = impact?.available_pairs ?? []
    if (!pairs.length) return null
    return pairs.find((pair) => pairKey(pair) === selectedPairKey) ?? pairs[0]
  }, [impact?.available_pairs, selectedPairKey])
  const suggestedKey = impact?.suggested_replacement ? pairKey(impact.suggested_replacement) : ''
  const selectedCaptureWorker = useMemo(() => {
    const workers = impact?.available_capture_workers ?? []
    if (!workers.length) return null
    return workers.find((item) => item.id === selectedCaptureWorkerId) ?? workers[0]
  }, [impact?.available_capture_workers, selectedCaptureWorkerId])
  const suggestedCaptureWorkerId = impact?.suggested_capture_worker?.id ?? ''
  const selectedSummarizeChoice = useMemo(() => {
    const models = impact?.available_summarize_models ?? []
    if (!models.length) return null
    return models.find((item) => item.summarize_model === selectedSummarizeModel) ?? models[0]
  }, [impact?.available_summarize_models, selectedSummarizeModel])
  const suggestedSummarizeModel = impact?.suggested_summarize_replacement?.summarize_model ?? ''

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const request = mode === 'delete'
      ? api<WorkerDeleteImpact>(`/workers/${worker.id}/delete-impact`)
      : api<WorkerDeleteImpact>(`/workers/${worker.id}/change-impact`, {
          method: 'POST',
          body: JSON.stringify(changeBody),
        })
    void request
      .then((data) => {
        if (!cancelled) setImpact(data)
      })
      .catch((error) => {
        if (!cancelled) {
          showError(error)
          onClose()
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [mode, worker.id, changeBody, onClose])

  useEffect(() => {
    if (!impact?.can_remediate || !impact.suggested_replacement) {
      setSelectedPairKey('')
    } else {
      setSelectedPairKey(pairKey(impact.suggested_replacement))
    }
    if (!impact?.can_remediate || !impact.suggested_summarize_replacement) {
      setSelectedSummarizeModel('')
    } else {
      setSelectedSummarizeModel(impact.suggested_summarize_replacement.summarize_model)
    }
    if (!impact?.can_remediate || !impact.suggested_capture_worker) {
      setSelectedCaptureWorkerId('')
    } else {
      setSelectedCaptureWorkerId(impact.suggested_capture_worker.id)
    }
    if (impact?.can_remediate) {
      setApplyRemediation(true)
    }
  }, [
    impact?.can_remediate,
    impact?.suggested_replacement,
    impact?.available_pairs,
    impact?.suggested_summarize_replacement,
    impact?.available_summarize_models,
    impact?.suggested_capture_worker,
    impact?.available_capture_workers,
  ])

  async function confirm() {
    setBusy(true)
    try {
      let remediation: WorkerRemediationPayload | undefined
      if (applyRemediation && impact?.can_remediate) {
        if (workerType === 'capture' && selectedCaptureWorker) {
          remediation = { capture_worker_id: selectedCaptureWorker.id }
        } else if (workerType === 'transcribe' && selectedPair) {
          remediation = {
            asr_model: selectedPair.asr_model,
            diarization_model: selectedPair.diarization_model ?? null,
          }
        } else if (workerType === 'summarize' && selectedSummarizeChoice) {
          remediation = { summarize_model: selectedSummarizeChoice.summarize_model }
        }
      }
      await onConfirm({ remediation })
      onClose()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  const title = mode === 'delete'
    ? t('instance.workerDeleteTitle', { name: workerLabel })
    : t('instance.workerChangeTitle', { name: workerLabel })

  return (
    <Modal
      onClose={() => {
        if (busy) return
        onClose()
      }}
      closeOnBackdrop={!busy && !loading}
      panelClassName="worker-impact-modal"
    >
      <header className="worker-impact-head">
        <h2>{title}</h2>
        <p className="worker-impact-subhead">
          <span className="badge">{t(`task.type.${workerType}`, { defaultValue: workerType })}</span>
          <span className="muted">{worker.base_url}</span>
        </p>
      </header>

      <div className="modal-body stack">
      {loading ? (
        <div className="worker-impact-banner loading" aria-busy="true">
          <p>{t('instance.workerImpactLoading')}</p>
        </div>
      ) : null}

      {!loading && impact ? (
        <>
          <div className={`worker-impact-banner ${impact.blocking ? 'warn' : 'ok'}`}>
            <p>
              {impact.blocking
                ? workerType === 'capture'
                  ? t('instance.workerImpactCaptureBlocking')
                  : t('instance.workerImpactBlocking')
                : t('instance.workerImpactNoImpact')}
            </p>
          </div>

          {impact.blocking || (workerType === 'capture' && (impact.capture_jitsi_hosts_count ?? 0) > 0) ? (
            <div className="worker-impact-sections">
              <ImpactSection
                title={t('instance.workerImpactUnavailableTitle')}
                hint={t('instance.workerImpactUnavailableHint')}
                empty={t('instance.workerImpactUnavailableEmpty')}
              >
                {unavailable.map((item, index) => (
                  <UnavailableRow key={index} item={item} t={t} />
                ))}
              </ImpactSection>

              <ImpactSection
                title={t('instance.workerImpactInUseTitle')}
                hint={t('instance.workerImpactInUseHint')}
                empty={t('instance.workerImpactInUseEmpty')}
              >
                {inUse.map((item, index) => (
                  <InUseRow key={index} item={item} t={t} />
                ))}
              </ImpactSection>
            </div>
          ) : null}

          {impact.can_remediate && workerType === 'transcribe' && selectedPair ? (
            <section className="worker-impact-remediation">
              <div className="worker-impact-section-head">
                <h3>{t('instance.workerImpactRemediationTitle')}</h3>
                <p className="muted worker-impact-section-hint">{t('instance.workerImpactRemediationHint')}</p>
              </div>
              <label className="worker-impact-remediation-apply">
                <input
                  type="checkbox"
                  checked={applyRemediation}
                  onChange={(e) => setApplyRemediation(e.target.checked)}
                  disabled={busy}
                />
                <span>{t('instance.workerImpactRemediationApply')}</span>
              </label>
              <label className="stack worker-impact-remediation-pair">
                <span>{t('instance.workerImpactRemediationPairLabel')}</span>
                <select
                  value={selectedPairKey}
                  onChange={(e) => setSelectedPairKey(e.target.value)}
                  disabled={busy || !applyRemediation}
                >
                  {(impact.available_pairs ?? []).map((pair) => {
                    const key = pairKey(pair)
                    const suggested = key === suggestedKey
                    return (
                      <option key={key} value={key}>
                        {formatPairLabel(pair, t)}
                        {suggested ? ` — ${t('instance.workerImpactRemediationSuggested')}` : ''}
                      </option>
                    )
                  })}
                </select>
              </label>
            </section>
          ) : null}

          {impact.can_remediate && workerType === 'summarize' && selectedSummarizeChoice ? (
            <section className="worker-impact-remediation">
              <div className="worker-impact-section-head">
                <h3>{t('instance.workerImpactSummarizeRemediationTitle')}</h3>
                <p className="muted worker-impact-section-hint">{t('instance.workerImpactSummarizeRemediationHint')}</p>
              </div>
              <label className="worker-impact-remediation-apply">
                <input
                  type="checkbox"
                  checked={applyRemediation}
                  onChange={(e) => setApplyRemediation(e.target.checked)}
                  disabled={busy}
                />
                <span>{t('instance.workerImpactSummarizeRemediationApply')}</span>
              </label>
              <label className="stack worker-impact-remediation-pair">
                <span>{t('instance.workerImpactSummarizeRemediationModelLabel')}</span>
                <select
                  value={selectedSummarizeModel}
                  onChange={(e) => setSelectedSummarizeModel(e.target.value)}
                  disabled={busy || !applyRemediation}
                >
                  {(impact.available_summarize_models ?? []).map((item: SummarizeModelChoice) => {
                    const suggested = item.summarize_model === suggestedSummarizeModel
                    return (
                      <option key={item.summarize_model} value={item.summarize_model}>
                        {item.summarize_model}
                        {suggested ? ` — ${t('instance.workerImpactRemediationSuggested')}` : ''}
                      </option>
                    )
                  })}
                </select>
              </label>
            </section>
          ) : null}

          {impact.can_remediate && workerType === 'capture' && selectedCaptureWorker ? (
            <section className="worker-impact-remediation">
              <div className="worker-impact-section-head">
                <h3>{t('instance.workerImpactCaptureRemediationTitle')}</h3>
                <p className="muted worker-impact-section-hint">{t('instance.workerImpactCaptureRemediationHint')}</p>
              </div>
              <label className="worker-impact-remediation-apply">
                <input
                  type="checkbox"
                  checked={applyRemediation}
                  onChange={(e) => setApplyRemediation(e.target.checked)}
                  disabled={busy}
                />
                <span>{t('instance.workerImpactCaptureRemediationApply')}</span>
              </label>
              <label className="stack worker-impact-remediation-pair">
                <span>{t('instance.workerImpactCaptureRemediationWorkerLabel')}</span>
                <select
                  value={selectedCaptureWorker.id}
                  onChange={(e) => setSelectedCaptureWorkerId(e.target.value)}
                  disabled={busy || !applyRemediation}
                >
                  {(impact.available_capture_workers ?? []).map((item) => {
                    const suggested = item.id === suggestedCaptureWorkerId
                    return (
                      <option key={item.id} value={item.id}>
                        {formatCaptureWorkerLabel(item)}
                        {item.base_url && item.name.trim() ? ` — ${item.base_url}` : ''}
                        {suggested ? ` — ${t('instance.workerImpactRemediationSuggested')}` : ''}
                      </option>
                    )
                  })}
                </select>
              </label>
            </section>
          ) : null}
        </>
      ) : null}
      </div>

      <div className="row modal-actions worker-impact-actions">
        <button type="button" disabled={busy || loading} autoFocus onClick={onClose}>
          {t('common.cancel')}
        </button>
        <button
          type="button"
          className={mode === 'delete' ? 'danger' : 'primary'}
          disabled={loading || busy}
          onClick={() => void confirm()}
        >
          {busy
            ? (mode === 'delete' ? t('instance.workerImpactDeleting') : t('instance.workerImpactBusy'))
            : mode === 'delete'
              ? t('instance.workerDeleteConfirm')
              : t('common.save')}
        </button>
      </div>
    </Modal>
  )
}
