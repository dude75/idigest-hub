import { useEffect, useMemo, useState } from 'react'
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
import { ConfirmDialog } from '../components/ConfirmDialog'
import { AppPageSizeField, AppSelectField } from '../components/app/AppFormControls'
import { allOption, pageSizeOptions } from '../components/app/selectOptions'
import { useTasksListPoll, type DoneStatusFilter } from '../hooks/useTasksListPoll'

const PAGE_SIZES = [10, 50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]

function taskHref(task: Task): string {
  if (task.status === 'success' && (task.type === 'import' || task.type === 'capture') && task.audio_id) {
    return `/app/audio/${task.audio_id}`
  }
  if (task.status === 'success' && task.transcript_id) return `/app/transcript/${task.transcript_id}`
  if (task.status === 'success' && task.summary_id) return `/app/summary/${task.summary_id}`
  return `/app/task/${task.task_id}`
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
  const [pageSize, setPageSize] = useState<PageSize>(10)
  const [page, setPage] = useState(0)
  const [orgs, setOrgs] = useState<Org[]>([])
  const [orgUsers, setOrgUsers] = useState<User[]>([])
  const [orgId, setOrgId] = useState('')
  const [userId, setUserId] = useState('')
  const [statusFilter, setStatusFilter] = useState<DoneStatusFilter>('')
  const [confirmPurge, setConfirmPurge] = useState(false)
  const [purgeBusy, setPurgeBusy] = useState(false)
  const instance = isInstanceAdmin(me)
  const admin = isOrgAdmin(me)
  const showOwner = instance || admin
  const showOrg = instance
  const showFilters = instance || admin

  const userOptions = useMemo(() => {
    if (instance) return uniqueUsers(orgs, orgId)
    return [...orgUsers].sort((a, b) => a.email.localeCompare(b.email))
  }, [instance, orgs, orgId, orgUsers])

  const { active, done, doneTotal, safePage, reload } = useTasksListPoll({
    orgId,
    userId,
    statusFilter,
    pageSize,
    page,
  })

  const pageCount = Math.max(1, Math.ceil(doneTotal / pageSize))
  const from = doneTotal === 0 ? 0 : safePage * pageSize + 1
  const to = Math.min(doneTotal, (safePage + 1) * pageSize)

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

  async function cancel(id: string) {
    try {
      await api(`/tasks/${id}`, { method: 'DELETE' })
      await reload()
    } catch (e) {
      showError(e)
    }
  }

  async function retry(id: string) {
    try {
      await api(`/tasks/${id}/retry`, { method: 'POST' })
      await reload()
    } catch (e) {
      showError(e)
    }
  }

  async function purgeHistory() {
    setPurgeBusy(true)
    try {
      const q = new URLSearchParams()
      if (orgId) q.set('org_id', orgId)
      if (userId) q.set('user_id', userId)
      if (statusFilter) q.set('status', statusFilter)
      const suffix = q.toString()
      await api<{ deleted: number }>(suffix ? `/tasks/purge?${suffix}` : '/tasks/purge', { method: 'POST' })
      setConfirmPurge(false)
      setPage(0)
      await reload(0, pageSize)
    } catch (e) {
      showError(e)
    } finally {
      setPurgeBusy(false)
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
      onValueChange={(v) => {
        setPageSize(Number(v) as PageSize)
        setPage(0)
      }}
      options={pageSizeOptions(PAGE_SIZES)}
    />
  )

  const statusFilterField = (
    <AppSelectField
      label={t('task.filterStatus')}
      htmlFor="tasks-filter-status"
      value={statusFilter}
      onValueChange={(next) => {
        setStatusFilter(next as DoneStatusFilter)
        setPage(0)
      }}
      options={[
        allOption(t('common.all')),
        { value: 'success', label: t('task.status.success') },
        { value: 'error', label: t('task.status.error') },
      ]}
    />
  )

  return (
    <AdminPage>
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

      {showFilters ? (
        <AppStackCard title={t('task.filters')}>
          <div className="stats-filters-fields">
            {instance ? (
              <AppSelectField
                label={t('task.filterOrg')}
                htmlFor="tasks-filter-org"
                value={orgId}
                onValueChange={(next) => {
                  const allowed = new Set(uniqueUsers(orgs, next).map((u) => u.id))
                  setOrgId(next)
                  if (userId && !allowed.has(userId)) setUserId('')
                  setPage(0)
                }}
                options={[
                  allOption(t('common.all')),
                  ...[...orgs].sort((a, b) => a.name.localeCompare(b.name)).map((org) => ({
                    value: org.id,
                    label: org.name,
                  })),
                ]}
              />
            ) : null}
            <AppSelectField
              label={t('task.filterUser')}
              htmlFor="tasks-filter-user"
              value={userId}
              onValueChange={(next) => {
                setUserId(next)
                setPage(0)
              }}
              options={[allOption(t('common.all')), ...userOptions.map((user) => ({ value: user.id, label: user.email }))]}
            />
            {statusFilterField}
          </div>
        </AppStackCard>
      ) : null}

      <ListSection
        title={t('task.done')}
        empty={t('common.empty')}
        isEmpty={doneTotal === 0}
        actions={
          <div className="flex flex-wrap items-end gap-3">
            {instance ? (
              <Button
                type="button"
                size="sm"
                variant="destructive"
                disabled={doneTotal === 0}
                onClick={() => setConfirmPurge(true)}
              >
                {t('task.purgeHistory')}
              </Button>
            ) : null}
            {pageSizeSelect}
          </div>
        }
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
      {confirmPurge ? (
        <ConfirmDialog
          message={t('task.purgeConfirm')}
          confirmLabel={t('task.purgeHistory')}
          danger
          busy={purgeBusy}
          onConfirm={() => void purgeHistory()}
          onClose={() => setConfirmPurge(false)}
        />
      ) : null}
    </AdminPage>
  )
}
