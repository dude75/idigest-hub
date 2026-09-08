import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isInstanceAdmin, isOrgAdmin, useAuth } from '../auth'
import type { Org, Task, User } from '../types'
import { ErrorBox, fmtDate } from '../util'

const ACTIVE = new Set(['queued', 'running'])
const PAGE_SIZES = [10, 50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]

function taskHref(task: Task): string {
  if (task.status === 'success' && task.transcript_id) return `/app/transcript/${task.transcript_id}`
  if (task.status === 'success' && task.summary_id) return `/app/summary/${task.summary_id}`
  return `/app/task/${task.task_id}`
}

function statusClass(status: string): string {
  if (status === 'success') return 'badge out'
  if (status === 'error') return 'badge err'
  if (status === 'running') return 'badge warn'
  return 'badge'
}

function tasksPath(orgId: string, userId: string): string {
  const q = new URLSearchParams()
  if (orgId) q.set('org_id', orgId)
  if (userId) q.set('user_id', userId)
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
  const [items, setItems] = useState<Task[]>([])
  const [err, setErr] = useState<unknown>(null)
  const [pageSize, setPageSize] = useState<PageSize>(10)
  const [page, setPage] = useState(0)
  const [orgs, setOrgs] = useState<Org[]>([])
  const [orgUsers, setOrgUsers] = useState<User[]>([])
  const [orgId, setOrgId] = useState('')
  const [userId, setUserId] = useState('')
  const instance = isInstanceAdmin(me)
  const admin = isOrgAdmin(me)
  const showOwner = instance || admin
  const showOrg = instance
  const showFilters = instance || admin

  const userOptions = useMemo(() => {
    if (instance) return uniqueUsers(orgs, orgId)
    return [...orgUsers].sort((a, b) => a.email.localeCompare(b.email))
  }, [instance, orgs, orgId, orgUsers])

  async function load() {
    try {
      const r = await api<{ items: Task[] }>(tasksPath(orgId, userId))
      setItems(r.items)
      setErr(null)
    } catch (e) {
      setErr(e)
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
        if (!stop) setErr(e)
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
    async function tick() {
      if (stop) return
      try {
        const r = await api<{ items: Task[] }>(tasksPath(orgId, userId))
        if (stop) return
        setItems(r.items)
        setErr(null)
        const active = r.items.some((item) => ACTIVE.has(item.status))
        timer = window.setTimeout(() => { void tick() }, active ? 1500 : 8000)
      } catch (e) {
        if (!stop) {
          setErr(e)
          timer = window.setTimeout(() => { void tick() }, 8000)
        }
      }
    }
    void tick()
    return () => {
      stop = true
      window.clearTimeout(timer)
    }
  }, [orgId, userId])

  async function cancel(id: string) {
    setErr(null)
    try {
      await api(`/tasks/${id}`, { method: 'DELETE' })
      await load()
    } catch (e) {
      setErr(e)
    }
  }

  const active = items.filter((item) => ACTIVE.has(item.status))
  const done = items.filter((item) => !ACTIVE.has(item.status))
  const pageCount = Math.max(1, Math.ceil(done.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const pagedDone = done.slice(safePage * pageSize, (safePage + 1) * pageSize)
  const from = done.length === 0 ? 0 : safePage * pageSize + 1
  const to = Math.min(done.length, (safePage + 1) * pageSize)

  function row(task: Task) {
    const canCancel = task.status === 'queued' && (admin || task.user_id === me?.user.id)
    const typeLabel = t(`task.type.${task.type}`, { defaultValue: task.type })
    const label = task.audio_filename || typeLabel
    return (
      <div className="item row" key={task.task_id}>
        <div className="grow">
          <Link className="title" to={taskHref(task)}>{label}</Link>
          <div className="muted">
            {task.audio_filename ? `${typeLabel} · ` : ''}
            {fmtDate(task.updated_at || task.created_at || '')}
            {showOwner && task.owner_email && ` · ${task.owner_email}`}
            {showOrg && task.org_name && ` · ${task.org_name}`}
          </div>
          {task.error && (
            <p className="err">{t(`errors.${task.error.code}`, { defaultValue: t('task.failed') })}</p>
          )}
        </div>
        <span className={statusClass(task.status)}>
          {t(`task.status.${task.status}`, { defaultValue: task.status })}
        </span>
        {canCancel && (
          <button type="button" onClick={() => void cancel(task.task_id)}>{t('task.cancel')}</button>
        )}
      </div>
    )
  }

  return (
    <div>
      <h1>{t('task.title')}</h1>
      <ErrorBox err={err} />
      {showFilters && (
        <div className="row filters">
          {instance && (
            <label>
              {t('task.filterOrg')}
              <select
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
                  <option key={org.id} value={org.id}>{org.name}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            {t('task.filterUser')}
            <select
              value={userId}
              onChange={(e) => {
                setUserId(e.target.value)
                setPage(0)
              }}
            >
              <option value="">{t('common.all')}</option>
              {userOptions.map((user) => (
                <option key={user.id} value={user.id}>{user.email}</option>
              ))}
            </select>
          </label>
        </div>
      )}
      <h2>{t('task.active')}</h2>
      <div className="list">
        {active.length === 0 && <p className="muted">{t('common.empty')}</p>}
        {active.map(row)}
      </div>
      <div className="row section-head">
        <h2>{t('task.done')}</h2>
        <label className="inline">
          {t('task.pageSize')}
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value) as PageSize)
              setPage(0)
            }}
          >
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="list">
        {done.length === 0 && <p className="muted">{t('common.empty')}</p>}
        {pagedDone.map(row)}
      </div>
      {done.length > pageSize && (
        <div className="row pager">
          <button type="button" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>
            {t('common.prev')}
          </button>
          <span className="muted">{t('task.pageRange', { from, to, total: done.length })}</span>
          <button type="button" disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>
            {t('common.next')}
          </button>
        </div>
      )}
    </div>
  )
}
