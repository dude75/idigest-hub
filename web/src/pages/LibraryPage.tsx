import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiUpload } from '../api'
import { isInstanceAdmin, isOrgAdmin, useAuth } from '../auth'
import { isLibraryTab, LIBRARY_DEFAULT, LIBRARY_FIRST_TAB, LIBRARY_TABS, libraryPath, type LibraryTab } from '../routes'
import { Button } from '@/components/ui/button'
import { AppCheckboxRow, AppInputField, AppPageSizeField, AppSelectField } from '../components/app/AppFormControls'
import { allOption, pageSizeOptions } from '../components/app/selectOptions'
import type {
  Audio,
  CapturePlatformsResponse,
  ImportPlatformsResponse,
  Summary,
  Task,
  Transcript,
  User,
  UserTag,
} from '../types'
import { AppStackCard } from '../components/AdminSection'
import { AdminTablePager } from '../components/app/AdminDataTable'
import { AppHoverHint } from '../components/app/AppHoverHint'
import { ListSection } from '../components/app/EntityUi'
import { IngestPipelinePanel } from '../components/IngestPipelinePanel'
import { ListRow } from '../components/ListRow'
import { Tabs } from '../components/Tabs'
import { Card, CardContent } from '@/components/ui/card'
import { AppSubmitButton } from '@/components/app/AdminUi'
import { Input } from '@/components/ui/input'
import { beginPipelineRun, captureRequest, endPipelineRun, importRequest, pipelineNavState, pipelineShouldTranscribe, transcribeRequest } from '../pipeline'
import { isVideoUploadFilename, UPLOAD_FILE_ACCEPT } from '../uploadFormats'
import { ApiError } from '../api'
import { TagManageDialog } from '../components/TagManageDialog'
import { MicrophoneRecordModal } from '../components/MicrophoneRecordModal'
import { MicIcon } from 'lucide-react'
import { AudioDerivedBadges, ShareBadges, TranscriptDerivedBadges, UserTagBadges, fmtDate, showError } from '../util'
import { captureMeetingNeedsPin, shouldRouteImportUrlToCapture } from '../util/captureHost'
import { MIC_RECORDING_TAG } from '../constants/userTags'

type SourceGroup<T> = {
  key: string
  sourceId: string | null
  items: T[]
}

const PAGE_SIZES = [10, 50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]

function librarySearchHaystack(tab: LibraryTab, item: Audio | Transcript | Summary): string {
  if (tab === 'audio') {
    const a = item as Audio
    return [a.filename, a.owner_email || ''].join(' ').toLowerCase()
  }
  if (tab === 'transcripts') {
    const tr = item as Transcript
    return [tr.display_title, tr.title, tr.source_filename, tr.owner_email].filter(Boolean).join(' ').toLowerCase()
  }
  const s = item as Summary
  return [s.display_title, s.title, s.source_transcript_title, s.owner_email].filter(Boolean).join(' ').toLowerCase()
}

function filterLibraryItems<T extends { owner_user_id: string }>(
  items: T[],
  tab: LibraryTab,
  query: string,
  userId: string,
): T[] {
  const q = query.trim().toLowerCase()
  return items.filter((item) => {
    if (userId && item.owner_user_id !== userId) return false
    if (!q) return true
    return librarySearchHaystack(tab, item as unknown as Audio | Transcript | Summary).includes(q)
  })
}

function groupBySource<T extends { created_at: string }>(
  items: T[],
  sourceIdOf: (item: T) => string | null | undefined,
): SourceGroup<T>[] {
  const map = new Map<string, T[]>()
  for (const item of items) {
    const key = sourceIdOf(item) || ''
    const list = map.get(key)
    if (list) list.push(item)
    else map.set(key, [item])
  }
  const groups: SourceGroup<T>[] = [...map.entries()].map(([key, grouped]) => ({
    key: key || 'none',
    sourceId: key || null,
    items: [...grouped].sort((a, b) => b.created_at.localeCompare(a.created_at)),
  }))
  groups.sort((a, b) => {
    const aDate = a.items[0]?.created_at || ''
    const bDate = b.items[0]?.created_at || ''
    if (aDate !== bDate) return bDate.localeCompare(aDate)
    return a.key.localeCompare(b.key)
  })
  return groups
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
  const [hiddenCount, setHiddenCount] = useState(0)
  const [audios, setAudios] = useState<Audio[]>([])
  const [transcripts, setTranscripts] = useState<Transcript[]>([])
  const [summaries, setSummaries] = useState<Summary[]>([])
  const [query, setQuery] = useState('')
  const [userId, setUserId] = useState('')
  const [orgUsers, setOrgUsers] = useState<User[]>([])
  const [groupListBySource, setGroupListBySource] = useState(false)
  const [pageSize, setPageSize] = useState<PageSize>(10)
  const [page, setPage] = useState(0)
  const [busy, setBusy] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{
    name: string
    percent: number
    phase: 'uploading' | 'processing'
    video: boolean
  } | null>(null)
  const [importUrl, setImportUrl] = useState('')
  const [importPlatforms, setImportPlatforms] = useState<ImportPlatformsResponse | null>(null)
  const [capturePin, setCapturePin] = useState('')
  const [capturePlatforms, setCapturePlatforms] = useState<CapturePlatformsResponse | null>(null)
  const [userTags, setUserTags] = useState<UserTag[]>([])
  const [manageTagsOpen, setManageTagsOpen] = useState(false)
  const [recordOpen, setRecordOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const hasOrg = Boolean(me?.org)
  const showOwnerFilter = isOrgAdmin(me) || isInstanceAdmin(me)

  function libraryListQuery() {
    const params = new URLSearchParams()
    if (hidden) params.set('include_hidden', 'true')
    if (tagFilter) params.set('tag', tagFilter)
    const qs = params.toString()
    return qs ? `?${qs}` : ''
  }

  async function loadUserTags() {
    try {
      const r = await api<{ items: UserTag[] }>('/tags')
      setUserTags(r.items)
    } catch (e) {
      showError(e)
    }
  }

  async function load(activeTab: LibraryTab = tab) {
    try {
      const q = libraryListQuery()
      if (activeTab === 'audio') {
        const r = await api<{ items: Audio[]; hidden_count: number }>(`/audios${q}`)
        setAudios(r.items)
        setHiddenCount(r.hidden_count ?? 0)
      } else if (activeTab === 'transcripts') {
        const r = await api<{ items: Transcript[]; hidden_count: number }>(`/transcripts${q}`)
        setTranscripts(r.items)
        setHiddenCount(r.hidden_count ?? 0)
      } else {
        const r = await api<{ items: Summary[]; hidden_count: number }>(`/summaries${q}`)
        setSummaries(r.items)
        setHiddenCount(r.hidden_count ?? 0)
      }
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    if (!hasOrg) return
    void load()
  }, [tab, hidden, tagFilter, hasOrg])

  useEffect(() => {
    if (!hasOrg) return
    void loadUserTags()
  }, [hasOrg, manageTagsOpen])

  useEffect(() => {
    setPage(0)
  }, [tab, hidden, tagFilter, query, userId, groupListBySource, pageSize])

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
        const r = await api<{ items: User[] }>('/org/users')
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
    () => filterLibraryItems(audios, 'audio', query, userId),
    [audios, query, userId],
  )
  const filteredTranscripts = useMemo(
    () => filterLibraryItems(transcripts, 'transcripts', query, userId),
    [transcripts, query, userId],
  )
  const filteredSummaries = useMemo(
    () => filterLibraryItems(summaries, 'summaries', query, userId),
    [summaries, query, userId],
  )
  const transcriptGroups = useMemo(
    () => groupBySource(filteredTranscripts, (tr) => tr.source_audio_id),
    [filteredTranscripts],
  )
  const summaryGroups = useMemo(
    () => groupBySource(filteredSummaries, (s) => s.source_transcript_id),
    [filteredSummaries],
  )

  const listTotal =
    tab === 'audio'
      ? filteredAudios.length
      : tab === 'transcripts'
        ? groupListBySource
          ? transcriptGroups.length
          : filteredTranscripts.length
        : groupListBySource
          ? summaryGroups.length
          : filteredSummaries.length
  const pageCount = Math.max(1, Math.ceil(listTotal / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const listOffset = safePage * pageSize
  const listFrom = listTotal === 0 ? 0 : listOffset + 1
  const listTo = Math.min(listTotal, listOffset + pageSize)
  const pagedAudios = filteredAudios.slice(listOffset, listOffset + pageSize)
  const pagedTranscripts = filteredTranscripts.slice(listOffset, listOffset + pageSize)
  const pagedTranscriptGroups = transcriptGroups.slice(listOffset, listOffset + pageSize)
  const pagedSummaries = filteredSummaries.slice(listOffset, listOffset + pageSize)
  const pagedSummaryGroups = summaryGroups.slice(listOffset, listOffset + pageSize)

  useEffect(() => {
    if (!sourceFilter) return
    const el = document.getElementById(`source-${sourceFilter}`)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    el.classList.add('group-highlight')
    const timer = window.setTimeout(() => el.classList.remove('group-highlight'), 2500)
    return () => window.clearTimeout(timer)
  }, [sourceFilter, tab, audios, transcripts, summaries])

  useEffect(() => {
    if (!hasOrg) return
    let cancelled = false
    async function loadPlatforms() {
      try {
        const data = await api<ImportPlatformsResponse>('/import/platforms')
        if (!cancelled) setImportPlatforms(data)
      } catch (e) {
        if (!cancelled) showError(e)
      }
    }
    void loadPlatforms()
    const timer = window.setInterval(() => void loadPlatforms(), 30_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [hasOrg])

  useEffect(() => {
    if (!hasOrg) return
    let cancelled = false
    async function loadCapturePlatforms() {
      try {
        const data = await api<CapturePlatformsResponse>('/capture/platforms')
        if (!cancelled) setCapturePlatforms(data)
      } catch (e) {
        if (!cancelled) showError(e)
      }
    }
    void loadCapturePlatforms()
    return () => {
      cancelled = true
    }
  }, [hasOrg])

  if (!hasOrg) return <Navigate to={me?.user.is_instance_admin ? '/app/instance' : '/app/profile'} replace />
  if (tabParam && !isLibraryTab(tabParam)) {
    return <Navigate to={LIBRARY_DEFAULT} replace />
  }

  async function submitCaptureUrl(url: string, pin: string) {
    const trimmed = url.trim()
    if (!trimmed) return
    setBusy(true)
    try {
      const pipeline = beginPipelineRun()
      const task = await api<Task>('/tasks/capture', {
        method: 'POST',
        body: JSON.stringify(captureRequest(trimmed, pin.trim(), pipeline)),
      })
      setCapturePin('')
      setImportUrl('')
      nav(`/app/task/${task.task_id}`, { state: pipelineNavState(pipeline, task) })
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function importFromUrl() {
    const url = importUrl.trim()
    if (!url) return
    if (shouldRouteImportUrlToCapture(url, captureEnabled)) {
      await submitCaptureUrl(url, capturePin)
      return
    }
    setBusy(true)
    try {
      const pipeline = beginPipelineRun()
      const task = await api<Task>('/tasks/import', {
        method: 'POST',
        body: JSON.stringify(importRequest(url, pipeline)),
      })
      setImportUrl('')
      nav(`/app/task/${task.task_id}`, { state: pipelineNavState(pipeline, task) })
    } catch (e) {
      if (
        captureEnabled &&
        e instanceof ApiError &&
        (e.code === 'meeting_use_capture' || e.code === 'unsupported_host') &&
        shouldRouteImportUrlToCapture(url, true)
      ) {
        await submitCaptureUrl(url, capturePin)
        return
      }
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function tagMicrophoneRecording(audioId: string): Promise<UserTag[]> {
    const r = await api<{ tags: UserTag[] }>('/object-tags', {
      method: 'PUT',
      body: JSON.stringify({
        object_type: 'audio',
        object_id: audioId,
        tags: [MIC_RECORDING_TAG],
      }),
    })
    return r.tags
  }

  async function upload(file: File, opts?: { fromMicrophone?: boolean }) {
    const pipeline = beginPipelineRun()
    setBusy(true)
    const video = isVideoUploadFilename(file.name)
    const fromMicrophone = Boolean(opts?.fromMicrophone)
    const serverExtract = video || fromMicrophone
    setUploadProgress({ name: file.name, percent: 0, phase: 'uploading', video: serverExtract })
    try {
      const body = new FormData()
      body.append('file', file)
      if (fromMicrophone) {
        body.append('from_microphone', 'true')
      }
      const item = await apiUpload<Audio>('/audios', body, (loaded, total) => {
        const percent = total ? Math.round((loaded / total) * 100) : 0
        setUploadProgress({
          name: file.name,
          percent,
          phase: percent >= 100 ? 'processing' : 'uploading',
          video: serverExtract,
        })
      })
      if (opts?.fromMicrophone) {
        try {
          item.user_tags = await tagMicrophoneRecording(item.id)
        } catch (e) {
          showError(e)
        }
      }
      if (pipelineShouldTranscribe(pipeline)) {
        const task = await api<Task>('/tasks/transcribe', {
          method: 'POST',
          body: JSON.stringify(transcribeRequest(item.id, pipeline)),
        })
        nav(`/app/task/${task.task_id}`, { state: pipelineNavState(pipeline, task) })
        return
      }
      endPipelineRun()
      nav(libraryPath('audio'))
      setAudios((prev) => [item, ...prev.filter((a) => a.id !== item.id)])
      await load('audio')
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
      setUploadProgress(null)
    }
  }

  const importEnabled = importPlatforms?.enabled === true
  const captureEnabled = capturePlatforms?.enabled === true
  const ingestEnabled = importEnabled || captureEnabled
  const trimmedIngestUrl = importUrl.trim()
  const ingestToCapture =
    captureEnabled &&
    trimmedIngestUrl.length > 0 &&
    shouldRouteImportUrlToCapture(trimmedIngestUrl, true)
  const showCapturePin =
    captureEnabled &&
    trimmedIngestUrl.length > 0 &&
    captureMeetingNeedsPin(trimmedIngestUrl, true)
  const proxyBlocked =
    importPlatforms?.download_proxy_required === true &&
    importPlatforms?.download_proxy_available === false
  const ingestSubmitDisabled =
    busy ||
    !trimmedIngestUrl ||
    (!ingestToCapture && (!importEnabled || proxyBlocked))
  const ingestUrlPlaceholder =
    importEnabled && captureEnabled
      ? t('library.ingestUrlPlaceholder')
      : captureEnabled
        ? t('library.capturePlaceholder')
        : t('library.importPlaceholder')
  const ingestSubmitLabel = busy
    ? ingestToCapture
      ? t('library.capturing')
      : t('library.importing')
    : ingestToCapture
      ? t('library.captureSubmit')
      : t('library.importSubmit')

  const listEmpty = listTotal === 0

  const pageSizeSelect = (
    <AppPageSizeField
      className="library-list-page-size"
      label={t('task.pageSize')}
      htmlFor="library-page-size"
      value={String(pageSize)}
      onValueChange={(v) => setPageSize(Number(v) as PageSize)}
      options={pageSizeOptions(PAGE_SIZES)}
    />
  )

  return (
    <div className="library-page">
      <Card className="library-ingest mb-4 font-sans bg-gradient-to-t from-primary/5 to-card shadow-xs dark:bg-card dark:bg-none">
        <CardContent className="flex flex-col gap-3 pt-6">
        {uploadProgress && (
          <div className="upload-progress library-ingest-progress" role="status" aria-live="polite">
            <div className="upload-progress-label">
              {uploadProgress.phase === 'processing'
                ? uploadProgress.video
                  ? t('library.uploadExtractingAudio', { name: uploadProgress.name })
                  : t('library.uploadProcessing', { name: uploadProgress.name })
                : t('library.uploading', { name: uploadProgress.name, percent: uploadProgress.percent })}
            </div>
            <div className="progress-bar" aria-hidden="true">
              <div
                className={`progress-bar-fill${uploadProgress.phase === 'processing' ? ' progress-bar-indeterminate' : ''}`}
                style={uploadProgress.phase === 'processing' ? undefined : { width: `${uploadProgress.percent}%` }}
              />
            </div>
          </div>
        )}
        <div className={`library-ingest-toolbar${ingestEnabled ? '' : ' upload-only'}`}>
          {ingestEnabled ? (
            <>
              <Input
                className="library-ingest-url bg-card"
                type="url"
                value={importUrl}
                placeholder={ingestUrlPlaceholder}
                disabled={busy}
                aria-label={t('library.ingestUrl')}
                onChange={(e) => setImportUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    if (!ingestSubmitDisabled) void importFromUrl()
                  }
                }}
              />
              {showCapturePin ? (
                <Input
                  className="library-capture-pin max-w-[8rem] bg-card"
                  type="password"
                  value={capturePin}
                  placeholder={t('library.capturePinPlaceholder')}
                  disabled={busy}
                  aria-label={t('library.capturePin')}
                  autoComplete="off"
                  onChange={(e) => setCapturePin(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      if (!ingestSubmitDisabled) void importFromUrl()
                    }
                  }}
                />
              ) : null}
              <AppSubmitButton ready={!ingestSubmitDisabled} busy={busy} onClick={() => void importFromUrl()}>
                {ingestSubmitLabel}
              </AppSubmitButton>
              <span className="library-ingest-or" aria-hidden="true">
                {t('library.or')}
              </span>
            </>
          ) : (
            <span className="library-ingest-upload-label">{t('library.uploadFile')}</span>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept={UPLOAD_FILE_ACCEPT}
            disabled={busy}
            className="profile-backup-file-input"
            aria-label={t('library.chooseFile')}
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void upload(f)
              e.target.value = ''
            }}
          />
          <AppHoverHint content={t('library.uploadFormatsHint')}>
            <Button
              type="button"
              variant="outline"
              className="shrink-0 whitespace-nowrap"
              disabled={busy}
              onClick={() => fileInputRef.current?.click()}
            >
              {t('library.chooseFile')}
            </Button>
          </AppHoverHint>
          <AppHoverHint content={t('library.recordMic')}>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="shrink-0"
              disabled={busy}
              aria-label={t('library.recordMic')}
              onClick={() => setRecordOpen(true)}
            >
              <MicIcon className="size-4" aria-hidden="true" />
            </Button>
          </AppHoverHint>
        </div>
        {importEnabled && importPlatforms && (proxyBlocked || importPlatforms.platforms.length > 0) && (
          <p className={proxyBlocked ? 'err library-ingest-hint' : 'muted library-ingest-hint'}>
            {proxyBlocked
              ? t('library.proxyUnavailable')
              : t('library.importHint', {
                  platforms: importPlatforms.platforms.map((p) => p.label).join(' · '),
                })}
          </p>
        )}
        <IngestPipelinePanel />
        </CardContent>
      </Card>
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
        actions={pageSizeSelect}
        footer={
          listTotal > pageSize ? (
            <AdminTablePager>
              <Button type="button" size="sm" variant="outline" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>
                {t('common.prev')}
              </Button>
              <span className="text-sm text-muted-foreground">{t('task.pageRange', { from: listFrom, to: listTo, total: listTotal })}</span>
              <Button type="button" size="sm" variant="outline" disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>
                {t('common.next')}
              </Button>
            </AdminTablePager>
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
            void load()
          }}
        />
      ) : null}
      {recordOpen ? (
        <MicrophoneRecordModal
          busy={busy}
          onClose={() => setRecordOpen(false)}
          onSave={(file) => {
            setRecordOpen(false)
            void upload(file, { fromMicrophone: true })
          }}
        />
      ) : null}
    </div>
  )
}
