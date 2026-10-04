import { useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { Task } from '../types'
import { PipelineProgress } from '../components/PipelineProgress'
import { isOrgAdmin, useAuth } from '../auth'
import { EntityDetailCard, EntityPage } from '../components/app/EntityUi'
import { AppSubmitButton } from '@/components/app/AdminUi'
import { Button } from '@/components/ui/button'
import { CardHeader, CardTitle } from '@/components/ui/card'
import { endPipelineRun, initialTaskFromNav, type PipelineNavState } from '../pipeline'
import {
  canCancelTask,
  isTaskMissingWorkerForModels,
  isTaskWaitingOnWorkers,
  taskStageLabel,
} from '../taskStage'
import { useTaskPoll } from '../hooks/useTaskPoll'
import { redirectAfterTaskSuccess } from '../taskPoll'
import { showError, taskErrorDetail, taskErrorMessage, taskIsRetriable, taskYoutubeClientsTried } from '../util'

export function TaskPage() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const navState = location.state as PipelineNavState | null
  const { t } = useTranslation()
  const { me } = useAuth()
  const nav = useNavigate()
  const admin = isOrgAdmin(me)
  const [pollGeneration, setPollGeneration] = useState(0)

  const { task, setTask } = useTaskPoll({
    taskId: id,
    enabled: Boolean(id),
    initialTask: initialTaskFromNav(navState, id) ?? null,
    followUpChain: true,
    generation: pollGeneration,
    errorToastId: 'task-poll',
    onSuccess: (finished) => {
      endPipelineRun()
      redirectAfterTaskSuccess(finished, nav)
    },
  })

  async function stopCapture() {
    if (!id) return
    try {
      const next = await api<Task>(`/tasks/${id}/stop`, { method: 'POST' })
      setTask(next)
    } catch (e) {
      showError(e)
    }
  }

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
      setPollGeneration((g) => g + 1)
    } catch (e) {
      showError(e)
    }
  }

  function taskHeading(): string {
    if (!task) return t('task.pipeline.loading')
    const stageLabel = taskStageLabel(task, t)
    if (stageLabel) return stageLabel
    if (task.status === 'queued' || task.status === 'running') {
      return t('task.working', { status: t(`task.status.${task.status}`, { defaultValue: task.status }) })
    }
    return t('task.working', { status: task.status })
  }

  const message = task ? taskErrorMessage(task, t) : null
  const detail = task ? taskErrorDetail(task) : null
  const clientsTried = task ? taskYoutubeClientsTried(task) : null
  const canManage = Boolean(task && (admin || task.user_id === me?.user.id))
  const cancelReady = Boolean(task && canCancelTask(task))

  return (
    <EntityPage backTo="/app/tasks">
      <EntityDetailCard>
        <CardHeader className="space-y-3 p-0 pb-2">
          <PipelineProgress task={task} />
          <CardTitle className="text-lg leading-snug">{taskHeading()}</CardTitle>
        </CardHeader>
        {task && isTaskWaitingOnWorkers(task) && cancelReady ? (
          <p className="muted task-wait-hint">{t('task.workerStage.waitHint')}</p>
        ) : null}
        {task && isTaskMissingWorkerForModels(task) ? (
          <p className="err task-wait-hint">
            {t('task.workerStage.noMatchingWorkerHint', {
              asr: typeof task.meta?.asr_model === 'string' ? task.meta.asr_model : '—',
              diarization:
                typeof task.meta?.diarization_model === 'string'
                  ? task.meta.diarization_model
                  : t('instance.diarizationOff'),
            })}
          </p>
        ) : null}
        {task?.type === 'import' && typeof task.meta?.platform === 'string' ? (
          <p className="muted">{task.meta.platform}</p>
        ) : null}
        {task?.error ? (
          <div className="flex flex-col gap-2">
            <p className="err">{message}</p>
            {clientsTried ? (
              <p className="muted import-error-meta">{t('task.youtubeClientsTried', { clients: clientsTried })}</p>
            ) : null}
            {detail ? (
              <details className="import-error-detail">
                <summary>{t('task.errorDetail')}</summary>
                <pre>{detail}</pre>
              </details>
            ) : null}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {task?.type === 'capture' &&
          task.status === 'running' &&
          task.meta?.worker_capture_status !== 'success' &&
          task.meta?.stage !== 'downloading' ? (
            <Button type="button" onClick={() => void stopCapture()}>{t('task.captureStop')}</Button>
          ) : null}
          {task && canManage && cancelReady ? (
            <AppSubmitButton ready onClick={() => void cancel()}>
              {t('task.cancel')}
            </AppSubmitButton>
          ) : null}
          {task && taskIsRetriable(task) && (admin || task.user_id === me?.user.id) ? (
            <Button type="button" onClick={() => void retry()}>{t('task.retry')}</Button>
          ) : null}
        </div>
      </EntityDetailCard>
    </EntityPage>
  )
}
