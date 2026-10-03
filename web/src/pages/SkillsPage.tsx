import { useEffect, useMemo, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AdminFormCard, AdminPage } from '../components/AdminSection'
import { AdminFormActions, AppSubmitButton, HubBadge } from '../components/app/AdminUi'
import { AdminTablePager } from '../components/app/AdminDataTable'
import { ListSection } from '../components/app/EntityUi'
import { ListRow } from '../components/ListRow'
import { StatCard, StatGrid } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import type { SchemaSkillListResponse, SchemaSkillPublicResponse } from '../openapi'
import { fmtDate, formatInteger, showError } from '../util'
import { Button } from '@/components/ui/button'
import { AppInputField, AppPageSizeField } from '../components/app/AppFormControls'
import { pageSizeOptions } from '../components/app/selectOptions'
import { AppField } from '../components/app/AppField'

const FILTERS = ['all', 'base', 'org', 'self', 'shared'] as const
const PAGE_SIZES = [10, 50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]

function skillBucket(skill: SchemaSkillPublicResponse): string {
  return skill.catalog || skill.scope
}

function skillScopeLabel(
  scope: string,
  catalog: string | null | undefined,
  t: (key: string) => string,
): string {
  if (catalog === 'shared' || scope === 'shared') return t('skills.shared')
  if (scope === 'base') return t('skills.base')
  if (scope === 'org') return t('skills.org')
  if (scope === 'self') return t('skills.self')
  return catalog || scope
}

export function SkillsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [allItems, setAllItems] = useState<NonNullable<SchemaSkillListResponse['items']>>([])
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('all')
  const [name, setName] = useState('')
  const [body, setBody] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)
  const [pageSize, setPageSize] = useState<PageSize>(10)
  const [page, setPage] = useState(0)
  const formRef = useRef<HTMLDivElement>(null)
  const admin = isOrgAdmin(me)
  const hasOrg = Boolean(me?.org)

  async function load() {
    const r = await api<SchemaSkillListResponse>('/skills')
    setAllItems(r.items ?? [])
  }

  useEffect(() => {
    if (!hasOrg) return
    load().catch(showError)
  }, [hasOrg])

  const items = useMemo(() => {
    const filtered =
      filter === 'all' ? allItems : allItems.filter((s) => skillBucket(s) === filter)
    return [...filtered].sort((a, b) => b.created_at.localeCompare(a.created_at))
  }, [allItems, filter])

  const listTotal = items.length
  const pageCount = Math.max(1, Math.ceil(listTotal / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const listFrom = listTotal === 0 ? 0 : safePage * pageSize + 1
  const listTo = Math.min(listTotal, (safePage + 1) * pageSize)
  const pagedItems = items.slice(safePage * pageSize, safePage * pageSize + pageSize)

  const summary = useMemo(() => ({
    total: allItems.length,
    self: allItems.filter((s) => skillBucket(s) === 'self').length,
    org: allItems.filter((s) => skillBucket(s) === 'org').length,
    shared: allItems.filter((s) => skillBucket(s) === 'shared').length,
  }), [allItems])

  if (!hasOrg) return <Navigate to="/app/profile" replace />

  function scrollToForm() {
    requestAnimationFrame(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  function openCreate() {
    setName('')
    setBody('')
    setFormOpen(true)
    scrollToForm()
  }

  function cancelCreate() {
    setName('')
    setBody('')
    setFormOpen(false)
  }

  async function create(kind: 'self' | 'org') {
    setCreateBusy(true)
    try {
      const path = kind === 'self' ? '/skills/self' : '/org/skills'
      await api(path, { method: 'POST', body: JSON.stringify({ name, body }) })
      cancelCreate()
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setCreateBusy(false)
    }
  }

  const pageSizeSelect = (
    <AppPageSizeField
      label={t('task.pageSize')}
      htmlFor="skills-page-size"
      value={String(pageSize)}
      onValueChange={(v) => {
        setPageSize(Number(v) as PageSize)
        setPage(0)
      }}
      options={pageSizeOptions(PAGE_SIZES)}
    />
  )

  return (
    <AdminPage>
      <Tabs
        items={FILTERS.map((f) => ({
          id: f,
          label: t(`skills.${f === 'all' ? 'all' : f}`),
          active: filter === f,
          onClick: () => {
            setFilter(f)
            setPage(0)
          },
        }))}
      />
      <StatGrid>
        <StatCard label={t('skills.statTotal')} value={formatInteger(summary.total)} tone="ops" />
        <StatCard label={t('skills.self')} value={formatInteger(summary.self)} tone="transcribe" />
        <StatCard label={t('skills.org')} value={formatInteger(summary.org)} tone="summarize" />
        <StatCard label={t('skills.shared')} value={formatInteger(summary.shared)} tone="audio" />
      </StatGrid>
      {formOpen ? (
        <div ref={formRef}>
          <AdminFormCard title={t('skills.createTitle')}>
            <AppInputField
              label={t('common.name')}
              htmlFor="skill-create-name"
              value={name}
              disabled={createBusy}
              onChange={(e) => setName(e.target.value)}
            />
            <AppField label={t('skills.body')} htmlFor="skill-create-body">
              <textarea
                id="skill-create-body"
                className="skill-editor"
                value={body}
                disabled={createBusy}
                onChange={(e) => setBody(e.target.value)}
              />
            </AppField>
            <AdminFormActions>
              <AppSubmitButton ready={Boolean(name.trim())} busy={createBusy} onClick={() => void create('self')}>
                {t('skills.newSelf')}
              </AppSubmitButton>
              {admin ? (
                <Button
                  type="button"
                  variant="outline"
                  disabled={createBusy || !name.trim()}
                  onClick={() => void create('org')}
                >
                  {t('skills.newOrg')}
                </Button>
              ) : null}
              <Button type="button" variant="outline" disabled={createBusy} onClick={cancelCreate}>
                {t('common.cancel')}
              </Button>
            </AdminFormActions>
          </AdminFormCard>
        </div>
      ) : null}
      <ListSection
        title={t('skills.catalog')}
        empty={t('common.empty')}
        isEmpty={listTotal === 0}
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <Button type="button" size="sm" onClick={openCreate}>
              {t('skills.createTitle')}
            </Button>
            {pageSizeSelect}
          </div>
        }
        footer={
          listTotal > pageSize ? (
            <AdminTablePager>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={safePage === 0}
                onClick={() => setPage(safePage - 1)}
              >
                {t('common.prev')}
              </Button>
              <span className="text-sm text-muted-foreground">
                {t('task.pageRange', { from: listFrom, to: listTo, total: listTotal })}
              </span>
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
        {pagedItems.map((s) => (
          <ListRow
            key={s.id}
            to={`/app/skill/${s.id}`}
            title={s.name}
            meta={fmtDate(s.created_at)}
            trailing={<HubBadge tone="muted">{skillScopeLabel(s.scope, s.catalog, t)}</HubBadge>}
          />
        ))}
      </ListSection>
    </AdminPage>
  )
}
