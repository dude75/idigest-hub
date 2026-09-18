import { useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AdminPage } from '../components/AdminSection'
import { ListRow } from '../components/ListRow'
import { StatCard, StatGrid } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import type { Skill } from '../types'
import { fmtDate, formatInteger, showError } from '../util'

const FILTERS = ['all', 'base', 'org', 'self', 'shared'] as const

function skillBucket(skill: Skill): string {
  return skill.catalog || skill.scope
}

function skillScopeLabel(scope: string, catalog: string | undefined, t: (key: string) => string): string {
  if (catalog === 'shared' || scope === 'shared') return t('skills.shared')
  if (scope === 'base') return t('skills.base')
  if (scope === 'org') return t('skills.org')
  if (scope === 'self') return t('skills.self')
  return catalog || scope
}

export function SkillsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [allItems, setAllItems] = useState<Skill[]>([])
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('all')
  const [name, setName] = useState('')
  const [body, setBody] = useState('')
  const admin = isOrgAdmin(me)
  const hasOrg = Boolean(me?.org)

  async function load() {
    const r = await api<{ items: Skill[] }>('/skills')
    setAllItems(r.items)
  }

  useEffect(() => {
    if (!hasOrg) return
    load().catch(showError)
  }, [hasOrg])

  const items = useMemo(() => {
    if (filter === 'all') return allItems
    return allItems.filter((s) => skillBucket(s) === filter)
  }, [allItems, filter])

  const summary = useMemo(() => ({
    total: allItems.length,
    self: allItems.filter((s) => skillBucket(s) === 'self').length,
    org: allItems.filter((s) => skillBucket(s) === 'org').length,
    shared: allItems.filter((s) => skillBucket(s) === 'shared').length,
  }), [allItems])

  if (!hasOrg) return <Navigate to="/app/profile" replace />

  async function create(kind: 'self' | 'org') {
    try {
      const path = kind === 'self' ? '/skills/self' : '/org/skills'
      await api(path, { method: 'POST', body: JSON.stringify({ name, body }) })
      setName('')
      setBody('')
      await load()
    } catch (e) {
      showError(e)
    }
  }

  return (
    <AdminPage>
      <Tabs
        items={FILTERS.map((f) => ({
          id: f,
          label: t(`skills.${f === 'all' ? 'all' : f}`),
          active: filter === f,
          onClick: () => setFilter(f),
        }))}
      />
      <StatGrid>
        <StatCard label={t('skills.statTotal')} value={formatInteger(summary.total)} tone="ops" />
        <StatCard label={t('skills.self')} value={formatInteger(summary.self)} tone="transcribe" />
        <StatCard label={t('skills.org')} value={formatInteger(summary.org)} tone="summarize" />
        <StatCard label={t('skills.shared')} value={formatInteger(summary.shared)} tone="audio" />
      </StatGrid>
      <details className="fold org-fold org-create-fold card">
        <summary className="org-fold-summary">
          <span>{t('skills.createTitle')}</span>
        </summary>
        <div className="stack fold-body">
          <label>
            {t('common.name')}
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            {t('skills.body')}
            <textarea className="skill-editor" value={body} onChange={(e) => setBody(e.target.value)} />
          </label>
          <div className="row">
            <button className="primary" type="button" onClick={() => void create('self')}>{t('skills.newSelf')}</button>
            {admin && <button type="button" onClick={() => void create('org')}>{t('skills.newOrg')}</button>}
          </div>
        </div>
      </details>
      <div className="card stack admin-list">
        <div className="stats-section-head">
          <h2>{t('skills.catalog')}</h2>
        </div>
        {items.length === 0 ? (
          <p className="stats-empty">{t('common.empty')}</p>
        ) : (
          <div className="list">
            {items.map((s) => (
              <ListRow
                key={s.id}
                to={`/app/skill/${s.id}`}
                title={s.name}
                meta={fmtDate(s.created_at)}
                trailing={<span className="badge">{skillScopeLabel(s.scope, s.catalog, t)}</span>}
              />
            ))}
          </div>
        )}
      </div>
    </AdminPage>
  )
}
