import type { NavigateFunction } from 'react-router-dom'
import { api } from './api'
import type { Task } from './types'

export const DEFAULT_TASK_POLL_MS = 1500
export const TASK_LIST_IDLE_POLL_MS = 8000
export const TASK_LIST_ACTIVE_POLL_MS = 1500

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

export function isActiveTaskStatus(status: string): boolean {
  return status === 'queued' || status === 'running'
}

export function isTerminalTaskStatus(status: string): boolean {
  return !isActiveTaskStatus(status)
}

export function followUpTaskId(task: Task): string | null {
  const id = task.meta?.follow_up_task_id
  return typeof id === 'string' && id.length > 0 ? id : null
}

export async function fetchTask(taskId: string): Promise<Task> {
  return api<Task>(`/tasks/${taskId}`)
}

export function redirectAfterTaskSuccess(task: Task, nav: NavigateFunction): void {
  if (task.summary_id) {
    nav(`/app/summary/${task.summary_id}`, { replace: true })
    return
  }
  if ((task.type === 'import' || task.type === 'capture') && task.audio_id) {
    nav(`/app/audio/${task.audio_id}`, { replace: true })
    return
  }
  if (task.transcript_id) {
    nav(`/app/transcript/${task.transcript_id}`, { replace: true })
  }
}
