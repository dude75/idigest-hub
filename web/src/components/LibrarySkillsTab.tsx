import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { AppStackCard } from './AdminSection'
import { AppListPagination } from './app/AppListPagination'
import { HubBadge } from './app/AdminUi'
import { AppSelectField } from './app/AppFormControls'
import {
  DEFAULT_LIST_PAGE_SIZE,
  listPageBounds,
  type ListPageSize,
} from './app/selectOptions'
import { ListSection } from './app/EntityUi'
import { ListRow } from './ListRow'
import type { SchemaSkillListResponse, SchemaSkillPublicResponse } from '../openapi'
import { fmtDate, showError } from '../util'
import { skillScopeLabel } from '../skillScope'
import { ButtonLink } from '@/components/ui/button-link'
const FILTERS = ['all', 'base', 'org', 'self', 'shared'] as const
type SkillFilter = (typeof FILTERS)[number]

function skillBucket(skill: SchemaSkillPublicResponse): string {
  return skill.catalog || skill.scope
}

export function LibrarySkillsTab() {
  const { t } = useTranslation()
  const [allItems, setAllItems] = useState<NonNullable<SchemaSkillListResponse['items']>>([])
  const [filter, setFilter] = useState<SkillFilter>('all')
  const [pageSize, setPageSize] = useState<ListPageSize>(DEFAULT_LIST_PAGE_SIZE)
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
  const { safePage, offset } = listPageBounds(listTotal, page, pageSize)
  const pagedItems = items.slice(offset, offset + pageSize)

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
        footer={
          listTotal > 0 ? (
            <AppListPagination
              htmlFor="library-skills-page-size"
              pageSize={pageSize}
              setPageSize={setPageSize}
              page={safePage}
              setPage={setPage}
              total={listTotal}
            />
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
