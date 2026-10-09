import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { AppStackCard } from './AdminSection'
import { AdminTablePager } from './app/AdminDataTable'
import { HubBadge } from './app/AdminUi'
import { AppPageSizeField, AppSelectField } from './app/AppFormControls'
import { pageSizeOptions } from './app/selectOptions'
import { ListSection } from './app/EntityUi'
import { ListRow } from './ListRow'
import type { SchemaSkillListResponse, SchemaSkillPublicResponse } from '../openapi'
import { fmtDate, showError } from '../util'
import { ButtonLink } from '@/components/ui/button-link'
import { Button } from '@/components/ui/button'

const FILTERS = ['all', 'base', 'org', 'self', 'shared'] as const
const PAGE_SIZES = [10, 50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]
type SkillFilter = (typeof FILTERS)[number]

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

export function LibrarySkillsTab() {
  const { t } = useTranslation()
  const [allItems, setAllItems] = useState<NonNullable<SchemaSkillListResponse['items']>>([])
  const [filter, setFilter] = useState<SkillFilter>('all')
  const [pageSize, setPageSize] = useState<PageSize>(10)
  const [page, setPage] = useState(0)

  useEffect(() => {
    void api<SchemaSkillListResponse>('/skills')
      .then((r) => setAllItems(r.items ?? []))
      .catch(showError)
  }, [])

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

  const pageSizeSelect = (
    <AppPageSizeField
      className="library-list-page-size"
      label={t('task.pageSize')}
      htmlFor="library-skills-page-size"
      value={String(pageSize)}
      onValueChange={(v) => {
        setPageSize(Number(v) as PageSize)
        setPage(0)
      }}
      options={pageSizeOptions(PAGE_SIZES)}
    />
  )

  return (
    <>
      <AppStackCard className="library-panel mb-4" contentClassName="pt-0">
        <div className="library-list-filters library-list-filters-skills">
          <AppSelectField
            className="library-skills-scope"
            expandMenu
            label={t('skills.filterScope')}
            htmlFor="library-skills-scope"
            value={filter}
            onValueChange={(v) => {
              setFilter(v as SkillFilter)
              setPage(0)
            }}
            options={FILTERS.map((f) => ({
              value: f,
              label: t(`skills.${f === 'all' ? 'all' : f}`),
            }))}
          />
          <div className="library-skills-new">
            <ButtonLink to="/app/skill/new" size="sm">
              {t('skills.createTitle')}
            </ButtonLink>
          </div>
        </div>
      </AppStackCard>
      <ListSection
        empty={t('common.empty')}
        isEmpty={listTotal === 0}
        actions={pageSizeSelect}
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
    </>
  )
}
