import type { Task } from './types'

type TaskTranslate = (
  key: string,
  opts?: Record<string, unknown> & { defaultValue?: string },
) => string

const HUB_WAIT_STAGES = new Set(['queued', 'waiting_engine', 'queue_full'])
const HUB_CONFIG_STAGES = new Set(['no_matching_worker'])

export function taskWorkStage(task: Task): string | null {
  if (task.type !== 'transcribe' && task.type !== 'summarize') return null
  if (task.status !== 'queued' && task.status !== 'running') return null
  const stage = typeof task.meta?.stage === 'string' ? task.meta.stage : null
  if (stage) return stage
  return task.status
}

export function isTaskMissingWorkerForModels(task: Task): boolean {
  return taskWorkStage(task) === 'no_matching_worker'
}

export function isTaskWaitingOnWorkers(task: Task): boolean {
  if (task.type !== 'transcribe' && task.type !== 'summarize') return false
  if (task.status === 'queued') {
    const stage = taskWorkStage(task)
    return stage != null && HUB_WAIT_STAGES.has(stage)
  }
  if (task.status === 'running') {
    const stage = taskWorkStage(task)
    return stage === 'queued' || stage === 'dispatched'
  }
  return false
}

export function isTaskProcessingOnWorker(task: Task): boolean {
  if (task.type !== 'transcribe' && task.type !== 'summarize') return false
  if (task.status !== 'running') return false
  const stage = taskWorkStage(task)
  return stage === 'running' || stage == null
}

export function taskStageLabelKey(task: Task): string | null {
  if (task.type === 'import') {
    const stage = typeof task.meta?.stage === 'string' ? task.meta.stage : task.status
    return `task.importStage.${stage}`
  }
  if (task.type === 'capture') {
    const stage = typeof task.meta?.stage === 'string' ? task.meta.stage : task.status
    return `task.captureStage.${stage}`
  }
  if (task.type !== 'transcribe' && task.type !== 'summarize') return null
  if (task.status !== 'queued' && task.status !== 'running') return null

  const stage = taskWorkStage(task)
  if (task.status === 'running' && stage === 'running') {
    return task.type === 'transcribe' ? 'task.pipeline.transcribing' : 'task.pipeline.summarizing'
  }
  if (task.status === 'running' && stage === 'queued') {
    return 'task.workerStage.worker_queue'
  }
  if (task.status === 'running' && stage === 'dispatched') {
    return 'task.workerStage.dispatched'
  }
  if (stage && (HUB_WAIT_STAGES.has(stage) || HUB_CONFIG_STAGES.has(stage))) {
    return `task.workerStage.${stage}`
  }
  if (task.status === 'queued') return 'task.workerStage.queued'
  if (task.status === 'running') {
    return task.type === 'transcribe' ? 'task.pipeline.transcribing' : 'task.pipeline.summarizing'
  }
  return null
}

export function taskStageLabel(task: Task, t: TaskTranslate): string | null {
  const key = taskStageLabelKey(task)
  if (!key) return null
  if (key.startsWith('task.importStage.') || key.startsWith('task.captureStage.')) {
    const title = typeof task.meta?.title === 'string' && task.meta.title ? `: ${task.meta.title}` : ''
    const translated = t(key, { title, defaultValue: '' })
    return translated || null
  }
  return t(key, { defaultValue: '' }) || null
}

export function taskStatusBadgeLabel(task: Task, t: TaskTranslate): string {
  if (task.status === 'error') return t('task.status.error')
  if (task.status === 'success') return t('task.status.success')
  const stageLabel = taskStageLabel(task, t)
  if (stageLabel) return stageLabel
  return t(`task.status.${task.status}`, { defaultValue: task.status })
}

export function taskStatusBadgeClass(task: Task): string {
  if (task.status === 'success') return 'badge out'
  if (task.status === 'error') return 'badge err'
  if (taskWorkStage(task) === 'no_matching_worker') return 'badge err'
  if (isTaskWaitingOnWorkers(task)) return 'badge wait'
  if (task.status === 'running') return 'badge warn'
  return 'badge'
}
