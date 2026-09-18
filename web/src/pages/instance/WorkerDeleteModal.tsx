import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { Modal } from '../../components/Modal'
import type { Worker, WorkerDeleteImpact } from '../../types'
import { formatInteger, showError } from '../../util'

type Props = {
  worker: Worker
  onClose: () => void
  onDeleted: () => void | Promise<void>
}

function formatModelPair(
  t: (key: string, opts?: Record<string, unknown>) => string,
  asr: string,
  diarization: string | null | undefined,
) {
  return t('instance.workerDeleteModelPair', {
    asr,
    diarization: diarization || t('instance.diarizationOff'),
  })
}

export function WorkerDeleteModal({ worker, onClose, onDeleted }: Props) {
  const { t } = useTranslation()
  const [impact, setImpact] = useState<WorkerDeleteImpact | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void api<WorkerDeleteImpact>(`/workers/${worker.id}/delete-impact`)
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
  }, [worker.id, onClose])

  const lines = useMemo(() => {
    if (!impact?.blocking) return []
    const out: string[] = []
    if (worker.type === 'transcribe') {
      out.push(t('instance.workerDeleteTranscribeRemaining', {
        count: formatInteger(impact.remaining_transcribe_workers ?? 0),
      }))
      for (const pair of impact.lost_model_pairs ?? []) {
        out.push(t('instance.workerDeleteLostPair', {
          pair: formatModelPair(t, pair.asr_model, pair.diarization_model),
        }))
      }
      if (impact.instance_defaults_broken) {
        out.push(t('instance.workerDeleteInstanceDefaults', {
          pair: formatModelPair(
            t,
            impact.instance_defaults?.asr_model ?? '—',
            impact.instance_defaults?.diarization_model,
          ),
        }))
      }
    } else {
      out.push(t('instance.workerDeleteSummarizeRemaining', {
        count: formatInteger(impact.remaining_summarize_workers ?? 0),
      }))
      if (impact.last_enabled_worker) {
        out.push(t('instance.workerDeleteLastSummarizeWorker'))
      }
    }
    const users = impact.affected_users ?? []
    if (users.length > 0) {
      const sample = users.slice(0, 3).map((user) => user.email).join(', ')
      const extra = users.length > 3 ? t('instance.workerDeleteUsersMore', { count: users.length - 3 }) : ''
      out.push(t('instance.workerDeleteAffectedUsers', { count: users.length, sample: `${sample}${extra}` }))
    }
    if ((impact.affected_tasks_count ?? 0) > 0) {
      out.push(t('instance.workerDeleteAffectedTasks', { count: impact.affected_tasks_count ?? 0 }))
    }
    return out
  }, [impact, t, worker.type])

  async function confirmDelete() {
    setBusy(true)
    try {
      await api(`/workers/${worker.id}`, { method: 'DELETE' })
      await onDeleted()
      onClose()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      onClose={() => {
        if (busy) return
        onClose()
      }}
      closeOnBackdrop={!busy}
      panelClassName="stack"
    >
      <h2>{t('instance.workerDeleteTitle', { name: worker.name || worker.base_url })}</h2>

      {loading ? <p className="muted">{t('instance.workerDeleteLoading')}</p> : null}

      {!loading && impact ? (
        <div className="stack">
          <p className={impact.blocking ? 'err' : 'muted'}>
            {impact.blocking ? t('instance.workerDeleteBlocking') : t('instance.workerDeleteNoImpact')}
          </p>
          {lines.length > 0 ? (
            <ul className="worker-delete-impact">
              {lines.map((line, index) => (
                <li key={index}>{line}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      <div className="row modal-actions">
        <button type="button" className="danger" disabled={loading || busy} onClick={() => void confirmDelete()}>
          {t('instance.workerDeleteConfirm')}
        </button>
        <button type="button" disabled={busy} autoFocus onClick={onClose}>
          {t('common.cancel')}
        </button>
      </div>
    </Modal>
  )
}
