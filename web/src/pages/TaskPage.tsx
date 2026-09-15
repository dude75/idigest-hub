import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { Task } from '../types'
import { PipelineProgress } from '../components/PipelineProgress'
import { isOrgAdmin, useAuth } from '../auth'
import {
  endPipelineRun,
  initialTaskFromNav,
  type PipelineNavState,
} from '../pipeline'
import { showError, taskErrorDetail, taskErrorMessage, taskIsRetriable, taskYoutubeClientsTried } from '../util'

const POLL_MS = 1500

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function followUpTaskId(task: Task): string | null {
  const id = task.meta?.follow_up_task_id
  return typeof id === 'string' && id.length > 0 ? id : null
}

function redirectAfterSuccess(task: Task, nav: ReturnType<typeof useNavigate>) {
  if (task.summary_id) {
    nav(`/app/summary/${task.summary_id}`, { replace: true })
    return
  }
  if (task.type === 'import' && task.audio_id) {
    nav(`/app/audio/${task.audio_id}`, { replace: true })
    return
  }
  if (task.transcript_id) {
    nav(`/app/transcript/${task.transcript_id}`, { replace: true })
  }
}

export function TaskPage() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const navState = location.state as PipelineNavState | null
  const { t } = useTranslation()
  const { me } = useAuth()
  const nav = useNavigate()
  const [task, setTask] = useState<Task | null>(() => initialTaskFromNav(navState, id))
  const admin = isOrgAdmin(me)

  useEffect(() => {
    if (!id) return
    let stop = false

    async function waitForTask(taskId: string): Promise<Task | null> {
      while (!stop) {
        const next = await api<Task>(`/tasks/${taskId}`)
        if (stop) return null
        setTask(next)
        if (next.status !== 'queued' && next.status !== 'running') return next
        await sleep(POLL_MS)
      }
      return null
    }

    async function run() {
      const taskId = id
      if (!taskId) return
      let current = await waitForTask(taskId)
      if (!current || stop) return

      while (current && current.status === 'success' && !stop) {
        const nextId = followUpTaskId(current)
        if (!nextId) break
        current = await waitForTask(nextId)
      }

      if (!current || stop || current.status !== 'success') return

      endPipelineRun()
      redirectAfterSuccess(current, nav)
    }

    void run().catch((e) => {
      if (!stop) showError(e, { id: 'task-poll' })
    })

    return () => {
      stop = true
    }
  }, [id, nav])

  async function cancel() {
    if (!id) return
    try {
      await api(`/tasks/${id}`, { method: 'DELETE' })
      endPipelineRun()
      nav('/app/tasks')
    } catch (e) {
      showError(e)
    }
  }

  async function retry() {
    if (!id) return
    try {
      const next = await api<Task>(`/tasks/${id}/retry`, { method: 'POST' })
      setTask(next)
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

  function taskHeading(): string {
    const importStage = importStageLabel()
    if (importStage) return importStage
    if (task && (task.status === 'queued' || task.status === 'running')) {
      if (task.type === 'transcribe') return t('task.pipeline.transcribing')
      if (task.type === 'summarize') return t('task.pipeline.summarizing')
      if (task.type === 'import') return t('task.importStage.queued')
    }
    if (!task) return t('task.pipeline.loading')
    return t('task.working', { status: task.status })
  }

  const message = task ? taskErrorMessage(task, t) : null
  const detail = task ? taskErrorDetail(task) : null
  const clientsTried = task ? taskYoutubeClientsTried(task) : null

  return (
    <div className="card stack">
      <Link to="/app/tasks">{t('common.back')}</Link>
      <PipelineProgress task={task} />
      <h1>{taskHeading()}</h1>
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
      {task && taskIsRetriable(task) && (admin || task.user_id === me?.user.id) && (
        <button type="button" onClick={() => void retry()}>{t('task.retry')}</button>
      )}
    </div>
  )
}
