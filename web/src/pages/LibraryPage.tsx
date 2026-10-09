import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type { SchemaOrgUserListResponse, SchemaUserTagListResponse } from '../openapi'
import { isInstanceAdmin, isOrgAdmin, useAuth } from '../auth'
import { isLibraryTab, LIBRARY_DEFAULT, LIBRARY_FIRST_TAB, LIBRARY_TABS, libraryPath, type LibraryTab } from '../routes'
import { Button } from '@/components/ui/button'
import { AppCheckboxRow, AppInputField, AppSelectField } from '../components/app/AppFormControls'
import { AppListPagination } from '../components/app/AppListPagination'
import {
  allOption,
  DEFAULT_LIST_PAGE_SIZE,
  listPageBounds,
  type ListPageSize,
} from '../components/app/selectOptions'
import type { Audio, Summary, Transcript, User } from '../types'
import { AppStackCard } from '../components/AdminSection'
import { ListSection } from '../components/app/EntityUi'
import { ListRow } from '../components/ListRow'
import { Tabs } from '../components/Tabs'
import { LibraryLinksTab } from '../components/LibraryLinksTab'
import { LibrarySkillsTab } from '../components/LibrarySkillsTab'
import { TagManageDialog } from '../components/TagManageDialog'
import { AudioDerivedBadges, ShareBadges, TranscriptDerivedBadges, UserTagBadges, fmtDate, showError } from '../util'
import { libraryServerSourceGrouping } from '../libraryList'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useLibraryList } from '../hooks/useLibraryList'

type SourceGroup<T> = {
  key: string
  sourceId: string | null
  items: T[]
}


export function LibraryPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const { tab: tabParam } = useParams<{ tab: string }>()
  const nav = useNavigate()
  const [searchParams] = useSearchParams()
  const sourceFilter = searchParams.get('source')
  const tagFilter = searchParams.get('tag') || ''
  const tab: LibraryTab = isLibraryTab(tabParam) ? tabParam : LIBRARY_FIRST_TAB
  const [hidden, setHidden] = useState(false)
  const [query, setQuery] = useState('')
  const [userId, setUserId] = useState('')
  const [orgUsers, setOrgUsers] = useState<User[]>([])
  const [groupListBySource, setGroupListBySource] = useState(false)
  const [pageSize, setPageSize] = useState<ListPageSize>(DEFAULT_LIST_PAGE_SIZE)
  const [page, setPage] = useState(0)
  const [userTags, setUserTags] = useState<NonNullable<SchemaUserTagListResponse['items']>>([])
  const [manageTagsOpen, setManageTagsOpen] = useState(false)
  const hasOrg = Boolean(me?.org)
  const showOwnerFilter = isOrgAdmin(me) || isInstanceAdmin(me)
  const debouncedQuery = useDebouncedValue(query, 300)
  const searchQ = debouncedQuery.trim() || undefined
  const serverSourceGrouping = libraryServerSourceGrouping(tab, groupListBySource)
  const serverOwnerId = showOwnerFilter && userId ? userId : undefined

  const { items, total: serverTotal, hiddenCount, sourceGroups, reload } = useLibraryList({
    tab,
    includeHidden: hidden,
    tag: tagFilter || null,
    ownerUserId: serverOwnerId,
    q: searchQ,
    groupBySource: serverSourceGrouping,
    limit: pageSize,
    offset: page * pageSize,
    enabled: hasOrg && tab !== 'skills' && tab !== 'links',
  })

  async function loadUserTags() {
    try {
      const r = await api<SchemaUserTagListResponse>('/tags')
      setUserTags(r.items ?? [])
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    if (!hasOrg) return
    void loadUserTags()
  }, [hasOrg, manageTagsOpen])

  useEffect(() => {
    setPage(0)
  }, [tab, hidden, tagFilter, debouncedQuery, userId, groupListBySource, pageSize])

  function setTagFilter(value: string) {
    const params = new URLSearchParams(searchParams)
    if (value) params.set('tag', value)
    else params.delete('tag')
    const qs = params.toString()
    nav(qs ? `${libraryPath(tab)}?${qs}` : libraryPath(tab))
  }

  function libraryNavPath(nextTab: LibraryTab) {
    return libraryPath(nextTab, { source: sourceFilter, tag: tagFilter || null })
  }

  useEffect(() => {
    if (!hasOrg || !showOwnerFilter) return
    let stop = false
    async function loadUsers() {
      try {
        const r = await api<SchemaOrgUserListResponse>('/org/users')
        if (!stop) setOrgUsers(r.items)
      } catch (e) {
        if (!stop) showError(e)
      }
    }
    void loadUsers()
    return () => {
      stop = true
    }
  }, [hasOrg, showOwnerFilter])

  const filteredAudios = useMemo(
    () => (tab === 'audio' ? (items as Audio[]) : []),
    [items, tab],
  )
  const filteredTranscripts = useMemo(
    () => (tab === 'transcripts' ? (items as Transcript[]) : []),
    [items, tab],
  )
  const filteredSummaries = useMemo(
    () => (tab === 'summaries' ? (items as Summary[]) : []),
    [items, tab],
  )
  const transcriptGroups = useMemo((): SourceGroup<Transcript>[] => {
    if (tab !== 'transcripts' || !groupListBySource) return []
    return (sourceGroups ?? []).map((g) => ({
      key: g.source_id || 'none',
      sourceId: g.source_id,
      items: g.items as Transcript[],
    }))
  }, [tab, groupListBySource, sourceGroups])
  const summaryGroups = useMemo((): SourceGroup<Summary>[] => {
    if (tab !== 'summaries' || !groupListBySource) return []
    return (sourceGroups ?? []).map((g) => ({
      key: g.source_id || 'none',
      sourceId: g.source_id,
      items: g.items as Summary[],
    }))
  }, [tab, groupListBySource, sourceGroups])

  const listTotal = serverTotal
  const { safePage } = listPageBounds(listTotal, page, pageSize)
  const pagedAudios = filteredAudios
  const pagedTranscripts = filteredTranscripts
  const pagedTranscriptGroups = transcriptGroups
  const pagedSummaries = filteredSummaries
  const pagedSummaryGroups = summaryGroups

  useEffect(() => {
    if (!sourceFilter) return
    const el = document.getElementById(`source-${sourceFilter}`)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    el.classList.add('group-highlight')
    const timer = window.setTimeout(() => el.classList.remove('group-highlight'), 2500)
    return () => window.clearTimeout(timer)
  }, [sourceFilter, tab, items])

  if (!hasOrg) return <Navigate to={me?.user.is_instance_admin ? '/app/instance' : '/app/profile'} replace />
  if (tabParam && !isLibraryTab(tabParam)) {
    return <Navigate to={LIBRARY_DEFAULT} replace />
  }

  const listEmpty = listTotal === 0

  return (
    <div className="library-page">
      <Tabs
        variant="default"
        className="library-tabs"
        ariaLabel={t('nav.library')}
        items={LIBRARY_TABS.map((id) => ({
          id,
          label: t(`library.${id}`),
          active: tab === id,
          onClick: () => nav(libraryNavPath(id)),
        }))}
      />
      {tab === 'links' ? (
        <LibraryLinksTab />
      ) : tab === 'skills' ? (
        <LibrarySkillsTab />
      ) : (
        <>
      <AppStackCard className="library-panel mb-4" contentClassName="pt-0">
        <div
          className={`library-list-filters${showOwnerFilter ? '' : ' library-list-filters-no-user'}`}
        >
          <AppInputField
            className="library-list-search"
            label={t('library.search')}
            htmlFor="library-list-search"
            type="search"
            value={query}
            placeholder={t('library.searchPlaceholder')}
            aria-label={t('library.search')}
            onChange={(e) => setQuery(e.target.value)}
          />
          {showOwnerFilter ? (
            <AppSelectField
              className="library-list-user"
              expandMenu
              label={t('task.filterUser')}
              htmlFor="library-list-user"
              value={userId}
              onValueChange={setUserId}
              options={[
                allOption(t('common.all')),
                ...[...orgUsers]
                  .sort((a, b) => a.email.localeCompare(b.email))
                  .map((user) => ({ value: user.id, label: user.email })),
              ]}
            />
          ) : null}
          <AppSelectField
            className="library-list-tag"
            expandMenu
            label={t('library.filterTag')}
            htmlFor="library-list-tag"
            value={tagFilter}
            onValueChange={setTagFilter}
            options={[
              allOption(t('common.all')),
              ...userTags.map((tag) => ({
                value: tag.id,
                label: `${tag.name}${tag.usage_count != null ? ` (${tag.usage_count})` : ''}`,
              })),
            ]}
          />
          <div className="library-list-tag-manage">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 shrink-0"
              onClick={() => setManageTagsOpen(true)}
            >
              {t('library.manageTags')}
            </Button>
          </div>
          <div className="library-list-toggles">
            <div className="library-list-toggles-row">
              <AppCheckboxRow
                id="library-group-by-source"
                className={`library-list-toggle${tab === 'audio' ? ' library-list-toggle-reserved' : ''}`}
                label={t('library.groupBySource')}
                checked={groupListBySource}
                disabled={tab === 'audio'}
                onCheckedChange={setGroupListBySource}
              />
              <AppCheckboxRow
                id="library-show-hidden"
                className="library-list-toggle"
                label={t('library.showHidden', { count: hiddenCount })}
                checked={hidden}
                onCheckedChange={setHidden}
              />
            </div>
          </div>
        </div>
      </AppStackCard>
      <ListSection
        empty={t('common.empty')}
        isEmpty={listEmpty}
        footer={
          !listEmpty ? (
            <AppListPagination
              htmlFor="library-page-size"
              pageSize={pageSize}
              setPageSize={setPageSize}
              page={safePage}
              setPage={setPage}
              total={listTotal}
            />
          ) : null
        }
      >
        {!listEmpty ? (
        <>
          {tab === 'audio' && (
            <>
              {pagedAudios.map((a) => (
                <ListRow
                  key={a.id}
                  to={`/app/audio/${a.id}`}
                  title={a.filename}
                  meta={
                    <>
                      <span>{fmtDate(a.created_at)}</span>
                      <AudioDerivedBadges audio={a} />
                      {a.owner_email && <span>· {a.owner_email}</span>}
                    </>
                  }
                  trailing={
                    <>
                      <UserTagBadges tags={a.user_tags} />
                      <ShareBadges item={a} />
                    </>
                  }
                />
              ))}
            </>
          )}
          {tab === 'transcripts' && groupListBySource && (
            <>
              {pagedTranscriptGroups.map((g) => (
                <section className="group" key={g.key} id={g.sourceId ? `source-${g.sourceId}` : undefined}>
                  <div className="group-title">
                    {g.sourceId ? (
                      <Link to={`/app/audio/${g.sourceId}`}>
                        {g.items[0]?.source_filename || t('transcript.sourceAudio', { id: g.sourceId.slice(0, 8) })}
                      </Link>
                    ) : (
                      <span className="muted">{t('transcript.noSource')}</span>
                    )}
                  </div>
                  {g.items.map((tr) => (
                    <ListRow
                      key={tr.id}
                      to={`/app/transcript/${tr.id}`}
                      title={tr.display_title || tr.title || tr.id.slice(0, 8)}
                      meta={
                        <>
                          <span>{fmtDate(tr.created_at)}</span>
                          <TranscriptDerivedBadges transcript={tr} />
                          {tr.owner_email && <span>· {tr.owner_email}</span>}
                        </>
                      }
                      trailing={
                        <>
                          <UserTagBadges tags={tr.user_tags} />
                          <ShareBadges item={tr} />
                        </>
                      }
                    />
                  ))}
                </section>
              ))}
            </>
          )}
          {tab === 'transcripts' && !groupListBySource && (
            <>
              {pagedTranscripts.map((tr) => (
                <ListRow
                  key={tr.id}
                  to={`/app/transcript/${tr.id}`}
                  title={tr.display_title || tr.title || tr.id.slice(0, 8)}
                  meta={
                    <>
                      <span>{fmtDate(tr.created_at)}</span>
                      <TranscriptDerivedBadges transcript={tr} />
                      {tr.source_audio_id && (
                        <>
                          <span>
                            {' · '}
                            <Link to={`/app/audio/${tr.source_audio_id}`}>
                              {tr.source_filename || t('transcript.sourceAudio', { id: tr.source_audio_id.slice(0, 8) })}
                            </Link>
                          </span>
                        </>
                      )}
                      {tr.owner_email && <span>· {tr.owner_email}</span>}
                    </>
                  }
                  trailing={
                    <>
                      <UserTagBadges tags={tr.user_tags} />
                      <ShareBadges item={tr} />
                    </>
                  }
                />
              ))}
            </>
          )}
          {tab === 'summaries' && groupListBySource && (
            <>
              {pagedSummaryGroups.map((g) => (
                <section className="group" key={g.key} id={g.sourceId ? `source-${g.sourceId}` : undefined}>
                  <div className="group-title">
                    {g.sourceId ? (
                      <Link to={`/app/transcript/${g.sourceId}`}>
                        {g.items[0]?.source_transcript_title ||
                          t('summary.sourceTranscript', { id: g.sourceId.slice(0, 8) })}
                      </Link>
                    ) : (
                      <span className="muted">{t('summary.noSource')}</span>
                    )}
                  </div>
                  {g.items.map((s) => (
                    <ListRow
                      key={s.id}
                      to={`/app/summary/${s.id}`}
                      title={s.display_title || s.title || s.id.slice(0, 8)}
                      meta={
                        <>
                          <span>{fmtDate(s.created_at)}</span>
                          {s.owner_email && <span>· {s.owner_email}</span>}
                        </>
                      }
                      trailing={
                        <>
                          <UserTagBadges tags={s.user_tags} />
                          <ShareBadges item={s} />
                        </>
                      }
                    />
                  ))}
                </section>
              ))}
            </>
          )}
          {tab === 'summaries' && !groupListBySource && (
            <>
              {pagedSummaries.map((s) => (
                <ListRow
                  key={s.id}
                  to={`/app/summary/${s.id}`}
                  title={s.display_title || s.title || s.id.slice(0, 8)}
                  meta={
                    <>
                      <span>{fmtDate(s.created_at)}</span>
                      {s.source_transcript_id && (
                        <span>
                          {' · '}
                          <Link to={`/app/transcript/${s.source_transcript_id}`}>
                            {s.source_transcript_title ||
                              t('summary.sourceTranscript', { id: s.source_transcript_id.slice(0, 8) })}
                          </Link>
                        </span>
                      )}
                      {s.owner_email && <span>· {s.owner_email}</span>}
                    </>
                  }
                  trailing={
                    <>
                      <UserTagBadges tags={s.user_tags} />
                      <ShareBadges item={s} />
                    </>
                  }
                />
              ))}
            </>
          )}
        </>
        ) : null}
      </ListSection>
      {manageTagsOpen ? (
        <TagManageDialog
          onClose={() => setManageTagsOpen(false)}
          onUpdated={() => {
            void loadUserTags()
            void reload()
          }}
        />
      ) : null}
        </>
      )}
    </div>
  )
}
