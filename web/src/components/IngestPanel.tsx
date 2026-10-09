import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Link2, MicIcon, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api, apiUpload, ApiError } from '../api'
import type {
  SchemaCapturePlatformsResponse,
  SchemaImportPlatformsResponse,
  SchemaUserTagListResponse,
} from '../openapi'
import { useAuth } from '../auth'
import { libraryPath } from '../routes'
import { Button } from '@/components/ui/button'
import { AppSubmitButton } from './app/AdminUi'
import { AppHoverHint } from './app/AppHoverHint'
import { IngestExtraTagsMultiSelect } from './IngestExtraTagsMultiSelect'
import { IngestPipelinePanel } from './IngestPipelinePanel'
import { MicrophoneRecordModal } from './MicrophoneRecordModal'
import { loadIngestExtraTags, saveIngestExtraTags } from '../ingestExtraTags'
import {
  beginPipelineRun,
  captureRequest,
  endPipelineRun,
  importRequest,
  pipelineNavState,
  pipelineShouldTranscribe,
  transcribeRequest,
} from '../pipeline'
import { isVideoUploadFilename, UPLOAD_FILE_ACCEPT } from '../uploadFormats'
import type { Audio, Task } from '../types'
import { showError } from '../util'
import { captureMeetingNeedsPin, shouldRouteImportUrlToCapture } from '../util/captureHost'
import { uploadMicrophoneRecording } from '../util/microphoneUpload'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'

type UploadProgress = {
  name: string
  percent: number
  phase: 'uploading' | 'processing'
  video: boolean
}

type IngestPanelProps = {
  layout?: 'studio' | 'toolbar'
}

export function IngestPanel({ layout = 'toolbar' }: IngestPanelProps) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const nav = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null)
  const [importUrl, setImportUrl] = useState('')
  const [ingestExtraTags, setIngestExtraTags] = useState(loadIngestExtraTags)
  const [importPlatforms, setImportPlatforms] = useState<SchemaImportPlatformsResponse | null>(null)
  const [capturePin, setCapturePin] = useState('')
  const [capturePlatforms, setCapturePlatforms] = useState<SchemaCapturePlatformsResponse | null>(null)
  const [userTags, setUserTags] = useState<NonNullable<SchemaUserTagListResponse['items']>>([])
  const [recordOpen, setRecordOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function loadPlatforms() {
      try {
        const data = await api<SchemaImportPlatformsResponse>('/import/platforms')
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
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadCapturePlatforms() {
      try {
        const data = await api<SchemaCapturePlatformsResponse>('/capture/platforms')
        if (!cancelled) setCapturePlatforms(data)
      } catch (e) {
        if (!cancelled) showError(e)
      }
    }
    void loadCapturePlatforms()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void api<SchemaUserTagListResponse>('/tags')
      .then((r) => setUserTags(r.items ?? []))
      .catch(showError)
  }, [])

  async function submitCaptureUrl(url: string, pin: string) {
    const trimmed = url.trim()
    if (!trimmed) return
    setBusy(true)
    try {
      const pipeline = beginPipelineRun()
      const task = await api<Task>('/tasks/capture', {
        method: 'POST',
        body: JSON.stringify(captureRequest(trimmed, pin.trim(), pipeline, me, ingestExtraTags)),
      })
      setCapturePin('')
      setImportUrl('')
      setIngestExtraTags([])
      saveIngestExtraTags([])
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
        body: JSON.stringify(importRequest(url, pipeline, me, ingestExtraTags)),
      })
      setImportUrl('')
      setIngestExtraTags([])
      saveIngestExtraTags([])
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
          body: JSON.stringify(transcribeRequest(item.id, pipeline, me)),
        })
        nav(`/app/task/${task.task_id}`, { state: pipelineNavState(pipeline, task) })
        return
      }
      endPipelineRun()
      nav(libraryPath('audio'))
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

  const importPlatformsHoverHint =
    importEnabled &&
    importPlatforms &&
    !proxyBlocked &&
    (importPlatforms.platforms ?? []).length > 0
      ? t('library.importHint', {
          platforms: (importPlatforms.platforms ?? []).map((p) => p.label).join(' · '),
        })
      : null

  const progressBlock = uploadProgress ? (
    <div className="upload-progress library-ingest-progress ingest-studio-progress" role="status" aria-live="polite">
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
  ) : null

  const fileInput = (
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
  )

  const micModal = recordOpen ? (
    <MicrophoneRecordModal
      busy={busy}
      onClose={() => setRecordOpen(false)}
      onSave={(file) => {
        setRecordOpen(false)
        setBusy(true)
        setUploadProgress({ name: file.name, percent: 0, phase: 'uploading', video: true })
        void uploadMicrophoneRecording(
          file,
          nav,
          {
            onProgress: (p) => setUploadProgress({ ...p, video: true }),
          },
          me,
        )
          .catch(showError)
          .finally(() => {
            setBusy(false)
            setUploadProgress(null)
          })
      }}
    />
  ) : null

  if (layout === 'studio') {
    return (
      <>
        <div className="ingest-studio">
          {progressBlock}
          <div className={cn('ingest-studio-grid', !ingestEnabled && 'ingest-studio-grid-no-link')}>
            {ingestEnabled ? (
              <section className="ingest-studio-card ingest-studio-card-link" aria-labelledby="ingest-from-link-title">
                <div className="ingest-studio-card-head">
                  <span className="ingest-studio-icon" aria-hidden="true">
                    <Link2 className="size-5" strokeWidth={1.75} />
                  </span>
                  <div>
                    <h2 id="ingest-from-link-title" className="ingest-studio-card-title">
                      {t('ingest.fromLink')}
                    </h2>
                    <p className="ingest-studio-card-hint">{t('ingest.fromLinkHint')}</p>
                  </div>
                </div>
                <div className="ingest-studio-card-body">
                  <AppHoverHint content={importPlatformsHoverHint} side="bottom">
                    <Input
                      className="ingest-studio-url bg-card"
                      type="url"
                      value={importUrl}
                      placeholder={ingestUrlPlaceholder}
                      disabled={busy}
                      aria-label={t('library.ingestUrl')}
                      aria-describedby={proxyBlocked ? 'ingest-studio-proxy-err' : undefined}
                      onChange={(e) => setImportUrl(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          if (!ingestSubmitDisabled) void importFromUrl()
                        }
                      }}
                    />
                  </AppHoverHint>
                  {proxyBlocked ? (
                    <p id="ingest-studio-proxy-err" className="err ingest-studio-inline-err" role="alert">
                      {t('library.proxyUnavailable')}
                    </p>
                  ) : null}
                  {showCapturePin ? (
                    <Input
                      className="ingest-studio-pin max-w-[10rem] bg-card"
                      type="password"
                      value={capturePin}
                      placeholder={t('library.capturePinPlaceholder')}
                      disabled={busy}
                      aria-label={t('library.capturePin')}
                      autoComplete="off"
                      onChange={(e) => setCapturePin(e.target.value)}
                    />
                  ) : null}
                  <IngestExtraTagsMultiSelect
                    catalog={userTags}
                    selected={ingestExtraTags}
                    disabled={busy}
                    onChange={(names) => {
                      setIngestExtraTags(names)
                      saveIngestExtraTags(names)
                    }}
                  />
                </div>
                <div className="ingest-studio-card-foot">
                  <AppSubmitButton
                    className="ingest-studio-foot-action w-full"
                    ready={!ingestSubmitDisabled}
                    busy={busy}
                    onClick={() => void importFromUrl()}
                  >
                    {ingestSubmitLabel}
                  </AppSubmitButton>
                </div>
              </section>
            ) : null}
            <section className="ingest-studio-card ingest-studio-card-file" aria-labelledby="ingest-from-file-title">
              <div className="ingest-studio-card-head">
                <span className="ingest-studio-icon ingest-studio-icon-soft" aria-hidden="true">
                  <Upload className="size-5" strokeWidth={1.75} />
                </span>
                <div>
                  <h2 id="ingest-from-file-title" className="ingest-studio-card-title">
                    {t('ingest.fromFile')}
                  </h2>
                  <p className="ingest-studio-card-hint">{t('ingest.fromFileHint')}</p>
                </div>
              </div>
              <div className="ingest-studio-card-body ingest-studio-card-body-grow">
                {fileInput}
                <button
                  type="button"
                  className="ingest-studio-dropzone ingest-studio-dropzone-hit"
                  disabled={busy}
                  aria-label={t('library.chooseFile')}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="size-8 text-muted-foreground/50" strokeWidth={1.25} aria-hidden="true" />
                </button>
              </div>
              <div className="ingest-studio-card-foot">
                <AppHoverHint content={t('library.uploadFormatsHint')} side="bottom">
                  <Button
                    type="button"
                    variant="outline"
                    className="ingest-studio-foot-action ingest-studio-file-btn w-full"
                    disabled={busy}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    {t('library.chooseFile')}
                  </Button>
                </AppHoverHint>
              </div>
            </section>
            <section className="ingest-studio-card ingest-studio-card-mic" aria-labelledby="ingest-from-mic-title">
              <div className="ingest-studio-card-head">
                <span className="ingest-studio-icon ingest-studio-icon-soft" aria-hidden="true">
                  <MicIcon className="size-5" strokeWidth={1.75} />
                </span>
                <div>
                  <h2 id="ingest-from-mic-title" className="ingest-studio-card-title">
                    {t('ingest.fromMic')}
                  </h2>
                  <p className="ingest-studio-card-hint">{t('ingest.fromMicHint')}</p>
                </div>
              </div>
              <div className="ingest-studio-card-body ingest-studio-card-body-grow">
                <button
                  type="button"
                  className="ingest-studio-dropzone ingest-studio-dropzone-hit"
                  disabled={busy}
                  aria-label={t('library.recordMic')}
                  onClick={() => setRecordOpen(true)}
                >
                  <MicIcon className="size-8 text-muted-foreground/50" strokeWidth={1.25} aria-hidden="true" />
                </button>
              </div>
              <div className="ingest-studio-card-foot">
                <Button
                  type="button"
                  variant="outline"
                  className="ingest-studio-foot-action ingest-studio-mic-btn w-full"
                  disabled={busy}
                  onClick={() => setRecordOpen(true)}
                >
                  <MicIcon className="size-4" aria-hidden="true" />
                  {t('library.recordMic')}
                </Button>
              </div>
            </section>
          </div>
          <section className="ingest-studio-card ingest-studio-card-pipeline" aria-labelledby="ingest-pipeline-title">
            <h2 id="ingest-pipeline-title" className="ingest-studio-pipeline-heading">
              {t('ingest.pipelineSection')}
            </h2>
            <IngestPipelinePanel className="ingest-studio-pipeline" defaultOpen />
          </section>
        </div>
        {micModal}
      </>
    )
  }

  return (
    <>
      <Card className="library-ingest font-sans shadow-md">
        <CardContent className="flex flex-col gap-3">
          {progressBlock}
          <div className={`library-ingest-toolbar${ingestEnabled ? '' : ' upload-only'}`}>
            {ingestEnabled ? (
              <>
                <div className="library-ingest-url-wrap">
                  <AppHoverHint content={importPlatformsHoverHint} side="bottom">
                    <Input
                      className="library-ingest-url bg-card"
                      type="url"
                      value={importUrl}
                      placeholder={ingestUrlPlaceholder}
                      disabled={busy}
                      aria-label={t('library.ingestUrl')}
                      aria-describedby={proxyBlocked ? 'library-ingest-proxy-err' : undefined}
                      onChange={(e) => setImportUrl(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          if (!ingestSubmitDisabled) void importFromUrl()
                        }
                      }}
                    />
                  </AppHoverHint>
                  {proxyBlocked ? (
                    <p id="library-ingest-proxy-err" className="err library-ingest-hint" role="alert">
                      {t('library.proxyUnavailable')}
                    </p>
                  ) : null}
                </div>
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
                <IngestExtraTagsMultiSelect
                  catalog={userTags}
                  selected={ingestExtraTags}
                  disabled={busy}
                  onChange={(names) => {
                    setIngestExtraTags(names)
                    saveIngestExtraTags(names)
                  }}
                />
                <AppSubmitButton ready={!ingestSubmitDisabled} busy={busy} onClick={() => void importFromUrl()}>
                  {ingestSubmitLabel}
                </AppSubmitButton>
                <Separator orientation="vertical" className="library-ingest-toolbar-separator" />
              </>
            ) : (
              <span className="library-ingest-upload-label">{t('library.uploadFile')}</span>
            )}
            {fileInput}
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
          <IngestPipelinePanel />
        </CardContent>
      </Card>
      {micModal}
    </>
  )
}
