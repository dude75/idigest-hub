import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Task } from '../types'
import {
  DEFAULT_TASK_POLL_MS,
  fetchTask,
  followUpTaskId,
  isActiveTaskStatus,
  sleep,
} from '../taskPoll'
import { showError } from '../util'

export type UseTaskPollOptions = {
  taskId: string | undefined
  enabled?: boolean
  pollMs?: number
  initialTask?: Task | null
  /** After success, poll follow_up_task_id until chain ends. */
  followUpChain?: boolean
  onTask?: (task: Task) => void
  onTerminal?: (task: Task) => void
  /** Called once when the chain finishes with success (after follow-ups). */
  onSuccess?: (task: Task) => void
  errorToastId?: string
  /** Bump to restart polling (e.g. after retry). */
  generation?: number
}

export function useTaskPoll(options: UseTaskPollOptions) {
  const {
    taskId,
    enabled = true,
    pollMs = DEFAULT_TASK_POLL_MS,
    initialTask = null,
    followUpChain = false,
    onTask,
    onTerminal,
    onSuccess,
    errorToastId,
    generation = 0,
  } = options

  const [task, setTask] = useState<Task | null>(initialTask)
  const onTaskRef = useRef(onTask)
  const onTerminalRef = useRef(onTerminal)
  const onSuccessRef = useRef(onSuccess)
  onTaskRef.current = onTask
  onTerminalRef.current = onTerminal
  onSuccessRef.current = onSuccess

  useEffect(() => {
    if (initialTask) setTask(initialTask)
  }, [taskId, initialTask])

  useEffect(() => {
    if (!taskId || !enabled) return
    let stop = false

    async function pollUntilTerminal(id: string): Promise<Task | null> {
      while (!stop) {
        try {
          const next = await fetchTask(id)
          if (stop) return null
          setTask(next)
          onTaskRef.current?.(next)
          if (!isActiveTaskStatus(next.status)) {
            onTerminalRef.current?.(next)
            return next
          }
          await sleep(pollMs)
        } catch (e) {
          if (!stop) {
            showError(e, errorToastId ? { id: errorToastId } : undefined)
          }
          await sleep(pollMs)
        }
      }
      return null
    }

    async function run() {
      let currentId: string | undefined = taskId
      while (currentId && !stop) {
        const result = await pollUntilTerminal(currentId)
        if (!result || stop) break
        if (result.status === 'success' && followUpChain) {
          const nextId = followUpTaskId(result)
          if (nextId) {
            currentId = nextId
            continue
          }
          onSuccessRef.current?.(result)
          break
        }
        if (result.status === 'success') {
          onSuccessRef.current?.(result)
        }
        break
      }
    }

    void run()
    return () => {
      stop = true
    }
  }, [taskId, enabled, pollMs, followUpChain, errorToastId, generation])

  async function refresh(): Promise<Task | null> {
    if (!taskId) return null
    try {
      const next = await api<Task>(`/tasks/${taskId}`)
      setTask(next)
      return next
    } catch (e) {
      showError(e)
      return null
    }
  }

  return { task, setTask, refresh }
}
