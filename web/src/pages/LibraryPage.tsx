import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiUpload } from '../api'
import { useAuth } from '../auth'
import { isLibraryTab, LIBRARY_DEFAULT, LIBRARY_FIRST_TAB, LIBRARY_TABS, libraryPath, type LibraryTab } from '../routes'
import type { Audio, CapturePlatformsResponse, ImportPlatformsResponse, Summary, Task, Transcript } from '../types'
import { IngestPipelinePanel } from '../components/IngestPipelinePanel'
import { ListRow } from '../components/ListRow'
import { Tabs } from '../components/Tabs'
import { beginPipelineRun, captureRequest, endPipelineRun, importRequest, pipelineNavState, pipelineShouldTranscribe, transcribeRequest } from '../pipeline'
import { isVideoUploadFilename, UPLOAD_FILE_ACCEPT } from '../uploadFormats'
import { ApiError } from '../api'
import { AudioDerivedBadges, ShareBadges, TranscriptDerivedBadges, fmtDate, showError } from '../util'
import { shouldRouteImportUrlToCapture } from '../util/captureHost'

type SourceGroup<T> = {
  key: string
  sourceId: string | null
  items: T[]
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
  const tab: LibraryTab = isLibraryTab(tabParam) ? tabParam : LIBRARY_FIRST_TAB
  const [hidden, setHidden] = useState(false)
  const [hiddenCount, setHiddenCount] = useState(0)
  const [audios, setAudios] = useState<Audio[]>([])
  const [transcripts, setTranscripts] = useState<Transcript[]>([])
  const [summaries, setSummaries] = useState<Summary[]>([])
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
  const hasOrg = Boolean(me?.org)

  async function load(activeTab: LibraryTab = tab) {
    try {
      const q = hidden ? '?include_hidden=true' : ''
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
  }, [tab, hidden, hasOrg])

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

  async function upload(file: File) {
    const pipeline = beginPipelineRun()
    setBusy(true)
    const video = isVideoUploadFilename(file.name)
    setUploadProgress({ name: file.name, percent: 0, phase: 'uploading', video })
    try {
      const body = new FormData()
      body.append('file', file)
      const item = await apiUpload<Audio>('/audios', body, (loaded, total) => {
        const percent = total ? Math.round((loaded / total) * 100) : 0
        setUploadProgress({
          name: file.name,
          percent,
          phase: percent >= 100 ? 'processing' : 'uploading',
          video,
        })
      })
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

  return (
    <div>
      <section className="card library-ingest">
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
              <input
                className="library-ingest-url"
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
              {ingestToCapture && (
                <input
                  className="library-capture-pin"
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
              )}
              <button
                type="button"
                className="primary"
                disabled={ingestSubmitDisabled}
                onClick={() => void importFromUrl()}
              >
                {ingestSubmitLabel}
              </button>
              <span className="library-ingest-or" aria-hidden="true">
                {t('library.or')}
              </span>
            </>
          ) : (
            <span className="library-ingest-upload-label">{t('library.uploadFile')}</span>
          )}
          <label
            className="btn library-file-btn"
            title={t('library.uploadFormatsHint')}
          >
            {t('library.chooseFile')}
            <input
              type="file"
              accept={UPLOAD_FILE_ACCEPT}
              disabled={busy}
              aria-label={t('library.chooseFile')}
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void upload(f)
                e.target.value = ''
              }}
            />
          </label>
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
      </section>
      <Tabs
        items={LIBRARY_TABS.map((id) => ({
          id,
          label: t(`library.${id}`),
          to: libraryPath(id),
        }))}
      />
      <label className="row" style={{ marginBottom: 12 }}>
        <input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} />
        {t('library.showHidden', { count: hiddenCount })}
      </label>
      {tab === 'audio' && (
        <div className="list">
          {audios.length === 0 && <p className="muted">{t('common.empty')}</p>}
          {audios.map((a) => (
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
              trailing={<ShareBadges item={a} />}
            />
          ))}
        </div>
      )}
      {tab === 'transcripts' && (
        <div className="list">
          {transcripts.length === 0 && <p className="muted">{t('common.empty')}</p>}
          {groupBySource(transcripts, (tr) => tr.source_audio_id).map((g) => (
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
                  trailing={<ShareBadges item={tr} />}
                />
              ))}
            </section>
          ))}
        </div>
      )}
      {tab === 'summaries' && (
        <div className="list">
          {summaries.length === 0 && <p className="muted">{t('common.empty')}</p>}
          {groupBySource(summaries, (s) => s.source_transcript_id).map((g) => (
            <section className="group" key={g.key} id={g.sourceId ? `source-${g.sourceId}` : undefined}>
              <div className="group-title">
                {g.sourceId ? (
                  <Link to={`/app/transcript/${g.sourceId}`}>
                    {g.items[0]?.source_transcript_title || t('summary.sourceTranscript', { id: g.sourceId.slice(0, 8) })}
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
                  trailing={<ShareBadges item={s} />}
                />
              ))}
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
