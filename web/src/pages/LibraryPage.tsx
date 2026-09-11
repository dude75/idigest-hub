import { useEffect, useState } from 'react'
import { Link, Navigate, NavLink, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, apiUpload } from '../api'
import { useAuth } from '../auth'
import { isLibraryTab, libraryPath, type LibraryTab } from '../routes'
import type { Audio, ImportPlatformsResponse, Summary, Task, Transcript } from '../types'
import { ShareBadges, fmtDate, showError } from '../util'

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
  const tab: LibraryTab = isLibraryTab(tabParam) ? tabParam : 'audio'
  const [hidden, setHidden] = useState(false)
  const [hiddenCount, setHiddenCount] = useState(0)
  const [audios, setAudios] = useState<Audio[]>([])
  const [transcripts, setTranscripts] = useState<Transcript[]>([])
  const [summaries, setSummaries] = useState<Summary[]>([])
  const [busy, setBusy] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{ name: string; percent: number } | null>(null)
  const [importUrl, setImportUrl] = useState('')
  const [importPlatforms, setImportPlatforms] = useState<ImportPlatformsResponse | null>(null)
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
    if (!hasOrg) return
    void api<ImportPlatformsResponse>('/import/platforms')
      .then(setImportPlatforms)
      .catch(showError)
  }, [hasOrg])

  if (!hasOrg) return <Navigate to={me?.user.is_instance_admin ? '/app/instance' : '/app/profile'} replace />
  if (tabParam && !isLibraryTab(tabParam)) {
    return <Navigate to={libraryPath('audio')} replace />
  }

  async function importFromUrl() {
    const url = importUrl.trim()
    if (!url) return
    setBusy(true)
    try {
      const task = await api<Task>('/tasks/import', {
        method: 'POST',
        body: JSON.stringify({ url }),
      })
      setImportUrl('')
      nav(`/app/task/${task.task_id}`)
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function upload(file: File) {
    setBusy(true)
    setUploadProgress({ name: file.name, percent: 0 })
    try {
      const body = new FormData()
      body.append('file', file)
      const item = await apiUpload<Audio>('/audios', body, (loaded, total) => {
        setUploadProgress({ name: file.name, percent: total ? Math.round((loaded / total) * 100) : 0 })
      })
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

  return (
    <div>
      <h1>{t('library.title')}</h1>
      <div className="tabs">
        {(['audio', 'transcripts', 'summaries'] as LibraryTab[]).map((id) => (
          <NavLink key={id} to={libraryPath(id)} className={({ isActive }) => (isActive ? 'active' : '')}>
            {t(`library.${id}`)}
          </NavLink>
        ))}
      </div>
      {tab === 'audio' && (
        <section className="card library-ingest">
          {uploadProgress && (
            <div className="upload-progress library-ingest-progress" role="status" aria-live="polite">
              <div className="upload-progress-label">
                {t('library.uploading', { name: uploadProgress.name, percent: uploadProgress.percent })}
              </div>
              <div className="progress-bar" aria-hidden="true">
                <div className="progress-bar-fill" style={{ width: `${uploadProgress.percent}%` }} />
              </div>
            </div>
          )}
          <div className={`library-ingest-toolbar${importEnabled ? '' : ' upload-only'}`}>
            {importEnabled && (
              <>
                <input
                  className="library-ingest-url"
                  type="url"
                  value={importUrl}
                  placeholder={t('library.importPlaceholder')}
                  disabled={busy}
                  aria-label={t('library.importUrl')}
                  onChange={(e) => setImportUrl(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      void importFromUrl()
                    }
                  }}
                />
                <button
                  type="button"
                  className="primary"
                  disabled={busy || !importUrl.trim()}
                  onClick={() => void importFromUrl()}
                >
                  {busy ? t('library.importing') : t('library.importSubmit')}
                </button>
                <span className="library-ingest-or" aria-hidden="true">
                  {t('library.or')}
                </span>
              </>
            )}
            {!importEnabled && (
              <span className="library-ingest-upload-label">{t('library.uploadFile')}</span>
            )}
            <label className="btn library-file-btn">
              {t('library.chooseFile')}
              <input
                type="file"
                accept=".wav,.mp3,.m4a,audio/wav,audio/mpeg,audio/mp4"
                disabled={busy}
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) void upload(f)
                  e.target.value = ''
                }}
              />
            </label>
          </div>
          {importEnabled && importPlatforms && importPlatforms.platforms.length > 0 && (
            <p className="muted library-ingest-hint">
              {t('library.importHint', {
                platforms: importPlatforms.platforms.map((p) => p.label).join(' · '),
              })}
            </p>
          )}
        </section>
      )}
      <label className="row" style={{ marginBottom: 12 }}>
        <input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} />
        {t('library.showHidden', { count: hiddenCount })}
      </label>
      {tab === 'audio' && (
        <div className="list">
          {audios.length === 0 && <p className="muted">{t('common.empty')}</p>}
          {audios.map((a) => (
            <div className="item row" key={a.id}>
              <div className="grow">
                <Link className="title" to={`/app/audio/${a.id}`}>{a.filename}</Link>
                <div className="muted">{fmtDate(a.created_at)} {a.owner_email && `· ${a.owner_email}`}</div>
              </div>
              <ShareBadges item={a} />
            </div>
          ))}
        </div>
      )}
      {tab === 'transcripts' && (
        <div className="list">
          {transcripts.length === 0 && <p className="muted">{t('common.empty')}</p>}
          {groupBySource(transcripts, (tr) => tr.source_audio_id).map((g) => (
            <section className="group" key={g.key}>
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
                <div className="item row" key={tr.id}>
                  <div className="grow">
                    <Link className="title" to={`/app/transcript/${tr.id}`}>
                      {tr.display_title || tr.title || tr.id.slice(0, 8)}
                    </Link>
                    <div className="muted">{fmtDate(tr.created_at)} {tr.owner_email && `· ${tr.owner_email}`}</div>
                  </div>
                  <ShareBadges item={tr} />
                </div>
              ))}
            </section>
          ))}
        </div>
      )}
      {tab === 'summaries' && (
        <div className="list">
          {summaries.length === 0 && <p className="muted">{t('common.empty')}</p>}
          {groupBySource(summaries, (s) => s.source_transcript_id).map((g) => (
            <section className="group" key={g.key}>
              <div className="group-title">
                {g.sourceId ? (
                  <Link to={`/app/transcript/${g.sourceId}`}>
                    {t('summary.sourceTranscript', { id: g.sourceId.slice(0, 8) })}
                  </Link>
                ) : (
                  <span className="muted">{t('summary.noSource')}</span>
                )}
              </div>
              {g.items.map((s) => (
                <div className="item row" key={s.id}>
                  <div className="grow">
                    <Link className="title" to={`/app/summary/${s.id}`}>
                      {s.display_title || s.title || s.id.slice(0, 8)}
                    </Link>
                    <div className="muted">{fmtDate(s.created_at)} {s.owner_email && `· ${s.owner_email}`}</div>
                  </div>
                  <ShareBadges item={s} />
                </div>
              ))}
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
