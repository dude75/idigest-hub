import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { Task } from '../types'
import { showError, taskErrorDetail, taskErrorMessage, taskYoutubeClientsTried } from '../util'

export function TaskPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const nav = useNavigate()
  const [task, setTask] = useState<Task | null>(null)

  useEffect(() => {
    if (!id) return
    let stop = false
    async function poll() {
      try {
        const next = await api<Task>(`/tasks/${id}`)
        if (stop) return
        setTask(next)
        if (next.status === 'queued' || next.status === 'running') {
          window.setTimeout(() => { void poll() }, 1500)
          return
        }
        if (next.status === 'success' && next.type === 'import' && next.audio_id) {
          nav(`/app/audio/${next.audio_id}`, { replace: true })
          return
        }
        if (next.transcript_id) {
          nav(`/app/transcript/${next.transcript_id}`, { replace: true })
          return
        }
        if (next.summary_id) {
          nav(`/app/summary/${next.summary_id}`, { replace: true })
        }
      } catch (e) {
        if (!stop) showError(e, { id: 'task-poll' })
      }
    }
    void poll()
    return () => { stop = true }
  }, [id, nav])

  async function cancel() {
    if (!id) return
    try {
      await api(`/tasks/${id}`, { method: 'DELETE' })
      nav('/app/tasks')
    } catch (e) {
      showError(e)
    }
  }

  function importStageLabel(): string | null {
    if (task?.type !== 'import') return null
    const stage = typeof task.meta?.stage === 'string' ? task.meta.stage : task.status
    const title = typeof task.meta?.title === 'string' && task.meta.title ? `: ${task.meta.title}` : ''
    const key = `task.importStage.${stage}`
    const translated = t(key, { title, defaultValue: '' })
    return translated || null
  }

  const stage = importStageLabel()
  const message = task ? taskErrorMessage(task, t) : null
  const detail = task ? taskErrorDetail(task) : null
  const clientsTried = task ? taskYoutubeClientsTried(task) : null

  return (
    <div className="card stack">
      <Link to="/app/tasks">{t('common.back')}</Link>
      <h1>{task?.type === 'import' && stage ? stage : t('task.working', { status: task?.status || '…' })}</h1>
      {task?.type === 'import' && typeof task.meta?.platform === 'string' && (
        <p className="muted">{task.meta.platform}</p>
      )}
      {task?.error && (
        <div className="stack">
          <p className="err">{message}</p>
          {clientsTried && (
            <p className="muted import-error-meta">{t('task.youtubeClientsTried', { clients: clientsTried })}</p>
          )}
          {detail && (
            <details className="import-error-detail">
              <summary>{t('task.errorDetail')}</summary>
              <pre>{detail}</pre>
            </details>
          )}
        </div>
      )}
      {task && (task.status === 'queued' || task.status === 'running') && (
        <button type="button" onClick={() => void cancel()}>{t('task.cancel')}</button>
      )}
    </div>
  )
}
