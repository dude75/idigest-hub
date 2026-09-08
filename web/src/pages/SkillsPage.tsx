import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import type { Skill } from '../types'
import { ErrorBox, fmtDate } from '../util'

const FILTERS = ['all', 'base', 'org', 'self', 'shared'] as const

export function SkillsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [items, setItems] = useState<Skill[]>([])
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('all')
  const [err, setErr] = useState<unknown>(null)
  const [name, setName] = useState('')
  const [body, setBody] = useState('')
  const admin = isOrgAdmin(me)
  const hasOrg = Boolean(me?.org)

  async function load() {
    const q = filter === 'all' ? '' : `?scope=${filter}`
    const r = await api<{ items: Skill[] }>(`/skills${q}`)
    setItems(r.items)
  }

  useEffect(() => {
    if (!hasOrg) return
    load().catch(setErr)
  }, [filter, hasOrg])

  const shown = useMemo(() => items, [items])
  if (!hasOrg) return <Navigate to="/app/profile" replace />

  async function create(kind: 'self' | 'org') {
    setErr(null)
    try {
      const path = kind === 'self' ? '/skills/self' : '/org/skills'
      await api(path, { method: 'POST', body: JSON.stringify({ name, body }) })
      setName('')
      setBody('')
      await load()
    } catch (e) {
      setErr(e)
    }
  }

  return (
    <div>
      <h1>{t('skills.title')}</h1>
      <div className="tabs">
        {FILTERS.map((f) => (
          <button key={f} type="button" className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>
            {t(`skills.${f === 'all' ? 'all' : f}`)}
          </button>
        ))}
      </div>
      <ErrorBox err={err} />
      <div className="card stack" style={{ marginBottom: 16 }}>
        <h2>{t('skills.newSelf')}</h2>
        <label>
          {t('common.name')}
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          {t('skills.body')}
          <textarea className="summary-editor" value={body} onChange={(e) => setBody(e.target.value)} />
        </label>
        <div className="row">
          <button className="primary" type="button" onClick={() => void create('self')}>{t('skills.newSelf')}</button>
          {admin && <button type="button" onClick={() => void create('org')}>{t('skills.newOrg')}</button>}
        </div>
      </div>
      <div className="list">
        {shown.length === 0 && <p className="muted">{t('common.empty')}</p>}
        {shown.map((s) => (
          <div className="item row" key={s.id}>
            <div className="grow">
              <Link className="title" to={`/app/skill/${s.id}`}>{s.name}</Link>
              <div className="muted">{fmtDate(s.created_at)}</div>
            </div>
            <span className="badge">{s.catalog || s.scope}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
