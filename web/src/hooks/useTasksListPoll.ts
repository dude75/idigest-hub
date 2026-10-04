import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../auth'
import { api } from '../api'
import type { TaskListResponse } from '../openapi/contracts'
import type { Task } from '../types'
import { TASK_LIST_ACTIVE_POLL_MS, TASK_LIST_IDLE_POLL_MS } from '../taskPoll'
import { showError } from '../util'

export type { TaskListResponse }

export type DoneStatusFilter = '' | 'success' | 'error'

type PageSize = 10 | 50 | 100

export function tasksListPath(
  orgId: string,
  userId: string,
  status: DoneStatusFilter,
  doneOffset: number,
  pageSize: PageSize,
): string {
  const q = new URLSearchParams()
  if (orgId) q.set('org_id', orgId)
  if (userId) q.set('user_id', userId)
  if (status) q.set('status', status)
  q.set('done_limit', String(pageSize))
  q.set('done_offset', String(doneOffset))
  return `/tasks?${q.toString()}`
}

export type UseTasksListPollOptions = {
  orgId: string
  userId: string
  statusFilter: DoneStatusFilter
  pageSize: PageSize
  page: number
  enabled?: boolean
  errorToastId?: string
}

export function useTasksListPoll(options: UseTasksListPollOptions) {
  const {
    orgId,
    userId,
    statusFilter,
    pageSize,
    page,
    enabled = true,
    errorToastId = 'tasks-poll',
  } = options

  const { refreshOrgWallet } = useAuth()
  const refreshOrgWalletRef = useRef(refreshOrgWallet)
  refreshOrgWalletRef.current = refreshOrgWallet
  const prevActiveIdsRef = useRef<Set<string>>(new Set())

  const [active, setActive] = useState<Task[]>([])
  const [done, setDone] = useState<Task[]>([])
  const [doneTotal, setDoneTotal] = useState(0)
  const fetchSeq = useRef(0)

  const pageCount = Math.max(1, Math.ceil(doneTotal / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const doneOffset = safePage * pageSize

  async function reload(offset = doneOffset, size: PageSize = pageSize) {
    const seq = ++fetchSeq.current
    try {
      const r = await api<TaskListResponse>(tasksListPath(orgId, userId, statusFilter, offset, size))
      if (seq !== fetchSeq.current) return
      setActive(r.active)
      setDone(r.done)
      setDoneTotal(r.done_total)
    } catch (e) {
      if (seq !== fetchSeq.current) return
      showError(e)
    }
  }

  useEffect(() => {
    if (!enabled) return
    let stop = false
    let timer = 0
    const offset = doneOffset

    async function tick() {
      if (stop) return
      const seq = ++fetchSeq.current
      try {
        const r = await api<TaskListResponse>(
          tasksListPath(orgId, userId, statusFilter, offset, pageSize),
        )
        if (stop || seq !== fetchSeq.current) return
        const nextActiveIds = new Set(r.active.map((task) => task.task_id))
        for (const taskId of prevActiveIdsRef.current) {
          if (!nextActiveIds.has(taskId)) {
            void refreshOrgWalletRef.current()
            break
          }
        }
        prevActiveIdsRef.current = nextActiveIds
        setActive(r.active)
        setDone(r.done)
        setDoneTotal(r.done_total)
        const delay = r.active.length > 0 ? TASK_LIST_ACTIVE_POLL_MS : TASK_LIST_IDLE_POLL_MS
        timer = window.setTimeout(() => {
          void tick()
        }, delay)
      } catch (e) {
        if (!stop && seq === fetchSeq.current) {
          showError(e, { id: errorToastId })
          timer = window.setTimeout(() => {
            void tick()
          }, TASK_LIST_IDLE_POLL_MS)
        }
      }
    }
    void tick()
    return () => {
      stop = true
      window.clearTimeout(timer)
    }
  }, [orgId, userId, statusFilter, pageSize, doneOffset, enabled, errorToastId])

  return { active, done, doneTotal, safePage, reload }
}
