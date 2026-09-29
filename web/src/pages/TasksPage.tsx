import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isInstanceAdmin, isOrgAdmin, useAuth } from '../auth'
import type { Org, Task, User } from '../types'
import { AdminPage, AppStackCard } from '../components/AdminSection'
import { ListSection } from '../components/app/EntityUi'
import { AdminRowActions, HubBadge } from '../components/app/AdminUi'
import { AdminTablePager } from '../components/app/AdminDataTable'
import { ListRow } from '../components/ListRow'
import {
  isTaskMissingWorkerForModels,
  isTaskWaitingOnWorkers,
  taskStatusBadgeLabel,
  taskStatusBadgeTone,
} from '../taskStage'
import { fmtDate, showError, taskErrorDetailBrief, taskErrorMessage, taskIsRetriable } from '../util'
import { Button } from '@/components/ui/button'
import { AppPageSizeField, AppSelectField } from '../components/app/AppFormControls'

const PAGE_SIZES = [10, 50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]

type TaskListResponse = {
  active: Task[]
  done: Task[]
  done_total: number
}

function taskHref(task: Task): string {
  if (task.status === 'success' && (task.type === 'import' || task.type === 'capture') && task.audio_id) {
    return `/app/audio/${task.audio_id}`
  }
  if (task.status === 'success' && task.transcript_id) return `/app/transcript/${task.transcript_id}`
  if (task.status === 'success' && task.summary_id) return `/app/summary/${task.summary_id}`
  return `/app/task/${task.task_id}`
}

function tasksPath(orgId: string, userId: string, doneOffset: number, pageSize: PageSize): string {
  const q = new URLSearchParams()
  if (orgId) q.set('org_id', orgId)
  if (userId) q.set('user_id', userId)
  q.set('done_limit', String(pageSize))
  q.set('done_offset', String(doneOffset))
  const s = q.toString()
  return s ? `/tasks?${s}` : '/tasks'
}

function uniqueUsers(orgs: Org[], orgId: string): User[] {
  const members = orgId
    ? (orgs.find((org) => org.id === orgId)?.members || [])
    : orgs.flatMap((org) => org.members || [])
  const seen = new Set<string>()
  const out: User[] = []
  for (const user of members) {
    if (seen.has(user.id)) continue
    seen.add(user.id)
    out.push(user)
  }
  return out.sort((a, b) => a.email.localeCompare(b.email))
}

export function TasksPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [active, setActive] = useState<Task[]>([])
  const [done, setDone] = useState<Task[]>([])
  const [doneTotal, setDoneTotal] = useState(0)
  const [pageSize, setPageSize] = useState<PageSize>(10)
  const [page, setPage] = useState(0)
  const [orgs, setOrgs] = useState<Org[]>([])
  const [orgUsers, setOrgUsers] = useState<User[]>([])
  const [orgId, setOrgId] = useState('')
  const [userId, setUserId] = useState('')
  const fetchSeq = useRef(0)
  const instance = isInstanceAdmin(me)
  const admin = isOrgAdmin(me)
  const showOwner = instance || admin
  const showOrg = instance
  const showFilters = instance || admin

  const userOptions = useMemo(() => {
    if (instance) return uniqueUsers(orgs, orgId)
    return [...orgUsers].sort((a, b) => a.email.localeCompare(b.email))
  }, [instance, orgs, orgId, orgUsers])

  const doneOffset = page * pageSize
  const pageCount = Math.max(1, Math.ceil(doneTotal / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const from = doneTotal === 0 ? 0 : safePage * pageSize + 1
  const to = Math.min(doneTotal, (safePage + 1) * pageSize)

  async function load(offset = doneOffset, size: PageSize = pageSize) {
    const seq = ++fetchSeq.current
    try {
      const r = await api<TaskListResponse>(tasksPath(orgId, userId, offset, size))
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
    if (!showFilters) return
    let stop = false
    async function loadFilters() {
      try {
        if (instance) {
          const r = await api<{ items: Org[] }>('/orgs')
          if (!stop) setOrgs(r.items)
        } else {
          const r = await api<{ items: User[] }>('/org/users')
          if (!stop) setOrgUsers(r.items)
        }
      } catch (e) {
        if (!stop) showError(e)
      }
    }
    void loadFilters()
    return () => {
      stop = true
    }
  }, [instance, showFilters])

  useEffect(() => {
    let stop = false
    let timer = 0
    const offset = safePage * pageSize

    async function tick() {
      if (stop) return
      const seq = ++fetchSeq.current
      try {
        const r = await api<TaskListResponse>(tasksPath(orgId, userId, offset, pageSize))
        if (stop || seq !== fetchSeq.current) return
        setActive(r.active)
        setDone(r.done)
        setDoneTotal(r.done_total)
        timer = window.setTimeout(() => { void tick() }, r.active.length > 0 ? 1500 : 8000)
      } catch (e) {
        if (!stop && seq === fetchSeq.current) {
          showError(e, { id: 'tasks-poll' })
          timer = window.setTimeout(() => { void tick() }, 8000)
        }
      }
    }
    void tick()
    return () => {
      stop = true
      window.clearTimeout(timer)
    }
  }, [orgId, userId, pageSize, safePage])

  async function cancel(id: string) {
    try {
      await api(`/tasks/${id}`, { method: 'DELETE' })
      await load()
    } catch (e) {
      showError(e)
    }
  }

  async function retry(id: string) {
    try {
      await api(`/tasks/${id}/retry`, { method: 'POST' })
      await load()
    } catch (e) {
      showError(e)
    }
  }

  function row(task: Task) {
    const canManage = admin || task.user_id === me?.user.id
    const canCancel = task.status === 'queued' && canManage
    const canRetry = taskIsRetriable(task) && canManage
    const typeLabel = t(`task.type.${task.type}`, { defaultValue: task.type })
    const label = task.audio_filename || typeLabel
    return (
      <ListRow
        key={task.task_id}
        to={taskHref(task)}
        title={label}
        meta={
          <>
            {task.audio_filename ? `${typeLabel} · ` : ''}
            {fmtDate(task.updated_at || task.created_at || '')}
            {showOwner && task.owner_email && ` · ${task.owner_email}`}
            {showOrg && task.org_name && ` · ${task.org_name}`}
          </>
        }
        belowMeta={
          task.error ? (
            <div className="task-row-error">
              <p className="err">{taskErrorMessage(task, t)}</p>
              {taskErrorDetailBrief(task) && (
                <p className="muted import-error-meta">{taskErrorDetailBrief(task)}</p>
              )}
            </div>
          ) : isTaskMissingWorkerForModels(task) ? (
            <p className="err task-row-hint">{t('task.workerStage.noMatchingWorkerShort')}</p>
          ) : isTaskWaitingOnWorkers(task) ? (
            <p className="muted task-row-hint">{t('task.workerStage.waitHintShort')}</p>
          ) : undefined
        }
        trailing={
          <AdminRowActions>
            <HubBadge tone={taskStatusBadgeTone(task)}>{taskStatusBadgeLabel(task, t)}</HubBadge>
            {canCancel ? (
              <Button type="button" size="sm" variant="outline" onClick={() => void cancel(task.task_id)}>
                {t('task.cancel')}
              </Button>
            ) : null}
            {canRetry ? (
              <Button type="button" size="sm" variant="outline" onClick={() => void retry(task.task_id)}>
                {t('task.retry')}
              </Button>
            ) : null}
          </AdminRowActions>
        }
      />
    )
  }

  const pageSizeSelect = (
    <AppPageSizeField
      label={t('task.pageSize')}
      htmlFor="tasks-page-size"
      value={String(pageSize)}
      onChange={(e) => {
        setPageSize(Number(e.target.value) as PageSize)
        setPage(0)
      }}
    >
      {PAGE_SIZES.map((n) => (
        <option key={n} value={n}>
          {n}
        </option>
      ))}
    </AppPageSizeField>
  )

  return (
    <AdminPage>
      {showFilters ? (
        <AppStackCard title={t('task.filters')}>
          <div className="stats-filters-fields">
            {instance ? (
              <AppSelectField
                label={t('task.filterOrg')}
                htmlFor="tasks-filter-org"
                value={orgId}
                onChange={(e) => {
                  const next = e.target.value
                  const allowed = new Set(uniqueUsers(orgs, next).map((u) => u.id))
                  setOrgId(next)
                  if (userId && !allowed.has(userId)) setUserId('')
                  setPage(0)
                }}
              >
                <option value="">{t('common.all')}</option>
                {[...orgs].sort((a, b) => a.name.localeCompare(b.name)).map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </AppSelectField>
            ) : null}
            <AppSelectField
              label={t('task.filterUser')}
              htmlFor="tasks-filter-user"
              value={userId}
              onChange={(e) => {
                setUserId(e.target.value)
                setPage(0)
              }}
            >
              <option value="">{t('common.all')}</option>
              {userOptions.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.email}
                </option>
              ))}
            </AppSelectField>
          </div>
        </AppStackCard>
      ) : null}

      <ListSection
        title={t('task.active')}
        empty={t('common.empty')}
        isEmpty={active.length === 0}
        actions={
          active.length > 0 ? (
            <HubBadge tone="primary">{t('task.activeCount', { count: active.length })}</HubBadge>
          ) : undefined
        }
      >
        {active.map(row)}
      </ListSection>

      <ListSection
        title={t('task.done')}
        empty={t('common.empty')}
        isEmpty={doneTotal === 0}
        actions={pageSizeSelect}
        footer={
          doneTotal > pageSize ? (
            <AdminTablePager>
              <Button type="button" size="sm" variant="outline" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>
                {t('common.prev')}
              </Button>
              <span className="text-sm text-muted-foreground">{t('task.pageRange', { from, to, total: doneTotal })}</span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={safePage >= pageCount - 1}
                onClick={() => setPage(safePage + 1)}
              >
                {t('common.next')}
              </Button>
            </AdminTablePager>
          ) : null
        }
      >
        {done.map(row)}
      </ListSection>
    </AdminPage>
  )
}
