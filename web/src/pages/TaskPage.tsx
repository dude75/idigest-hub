import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { Task } from '../types'
import { ErrorBox } from '../util'

export function TaskPage() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const nav = useNavigate()
  const [task, setTask] = useState<Task | null>(null)
  const [err, setErr] = useState<unknown>(null)

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
        if (next.transcript_id) {
          nav(`/app/transcript/${next.transcript_id}`, { replace: true })
          return
        }
        if (next.summary_id) {
          nav(`/app/summary/${next.summary_id}`, { replace: true })
        }
      } catch (e) {
        if (!stop) setErr(e)
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
      setErr(e)
    }
  }

  return (
    <div className="card stack">
      <Link to="/app/tasks">{t('common.back')}</Link>
      <h1>{t('task.working', { status: task?.status || '…' })}</h1>
      <ErrorBox err={err} />
      {task?.error && <p className="err">{t(`errors.${task.error.code}`, { defaultValue: t('task.failed') })}</p>}
      {task?.status === 'queued' && (
        <button type="button" onClick={() => void cancel()}>{t('task.cancel')}</button>
      )}
    </div>
  )
}
