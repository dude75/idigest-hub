import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
import { IngestStudioIconHit } from './IngestStudioIconHit'
import { IngestStudioLinkField } from './IngestStudioLinkField'
import { MicrophoneRecordModal } from './MicrophoneRecordModal'
import { appendIngestUserTagsToForm } from '../ingestUserTagsForm'
import { useIngestExtraTagsSlot } from '../hooks/useIngestExtraTagsSlot'
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
import {
  captureMeetingNeedsPin,
  ingestLinkUrlLooksInvalid,
  shouldRouteImportUrlToCapture,
} from '../util/captureHost'
import { studioLinkSubmitLabel } from '../util/ingestLinkSubmitLabel'
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
  const linkExtraTags = useIngestExtraTagsSlot('link')
  const fileExtraTags = useIngestExtraTagsSlot('file')
  const micExtraTags = useIngestExtraTagsSlot('mic')
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
        body: JSON.stringify(captureRequest(trimmed, pin.trim(), pipeline, me, linkExtraTags.tags)),
      })
      setCapturePin('')
      setImportUrl('')
      linkExtraTags.reset()
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
        body: JSON.stringify(importRequest(url, pipeline, me, linkExtraTags.tags)),
      })
      setImportUrl('')
      linkExtraTags.reset()
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
      appendIngestUserTagsToForm(body, fileExtraTags.tags)
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
        fileExtraTags.reset()
        nav(`/app/task/${task.task_id}`, { state: pipelineNavState(pipeline, task) })
        return
      }
      endPipelineRun()
      fileExtraTags.reset()
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

  const studioLinkSubmit = studioLinkSubmitLabel(t, trimmedIngestUrl, busy, ingestToCapture)

  const ingestUrlHoverHint = useMemo((): ReactNode => {
    const lines: string[] = []
    if (importEnabled && importPlatforms && !proxyBlocked) {
      const labels = (importPlatforms.platforms ?? []).map((p) => p.label)
      if (labels.length) {
        lines.push(t('library.importHint', { platforms: labels.join(' · ') }))
      }
    }
    if (captureEnabled && capturePlatforms) {
      const meetingLabels = (capturePlatforms.connectors ?? [])
        .map((c) => String(c.label || c.id || '').trim())
        .filter(Boolean)
      if (meetingLabels.length) {
        lines.push(t('ingest.linkHoverMeetings', { platforms: meetingLabels.join(' · ') }))
      }
    }
    if (lines.length === 0) return null
    if (lines.length === 1) return lines[0]
    return (
      <span className="flex flex-col gap-1.5">
        {lines.map((line) => (
          <span key={line}>{line}</span>
        ))}
      </span>
    )
  }, [captureEnabled, capturePlatforms, importEnabled, importPlatforms, proxyBlocked, t])

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
            clearExtraTags: micExtraTags.reset,
          },
          me,
          micExtraTags.tags,
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
              <section
                className="ingest-studio-card ingest-studio-card-ingest ingest-studio-card-link"
                aria-labelledby="ingest-from-link-title"
              >
                <div className="ingest-studio-card-head">
                  <span className="ingest-studio-icon ingest-studio-icon-soft" aria-hidden="true">
                    <Link2 className="size-5" strokeWidth={1.75} />
                  </span>
                  <div>
                    <h2 id="ingest-from-link-title" className="ingest-studio-card-title">
                      {t('ingest.fromLink')}
                    </h2>
                    <p className="ingest-studio-card-hint">{t('ingest.fromLinkHint')}</p>
                  </div>
                </div>
                <div
                  className={cn(
                    'ingest-studio-card-body ingest-studio-card-body-grow ingest-studio-card-ingest-body',
                    showCapturePin && 'ingest-studio-card-body-has-pin',
                  )}
                >
                  <div className="ingest-studio-card-main-slot">
                    <AppHoverHint
                      className="ingest-studio-link-hint"
                      content={ingestUrlHoverHint}
                      side="bottom"
                    >
                      <IngestStudioLinkField
                        className="ingest-studio-main-hit h-full min-h-0 w-full"
                        value={importUrl}
                        placeholder={ingestUrlPlaceholder}
                        disabled={busy}
                        describedBy={
                          [
                            proxyBlocked ? 'ingest-studio-proxy-err' : undefined,
                            ingestLinkUrlLooksInvalid(importUrl) ? 'ingest-studio-link-err' : undefined,
                          ]
                            .filter(Boolean)
                            .join(' ') || undefined
                        }
                        onChange={setImportUrl}
                        onSubmit={() => {
                          if (!ingestSubmitDisabled) void importFromUrl()
                        }}
                      />
                    </AppHoverHint>
                  </div>
                  {showCapturePin ? (
                    <div className="ingest-studio-pin-slot">
                      <Input
                        className="ingest-studio-pin h-full max-w-none bg-card"
                        type="password"
                        value={capturePin}
                        placeholder={t('library.capturePinPlaceholder')}
                        disabled={busy}
                        aria-label={t('library.capturePin')}
                        autoComplete="off"
                        onChange={(e) => setCapturePin(e.target.value)}
                      />
                    </div>
                  ) : null}
                </div>
                <div className="ingest-studio-card-foot">
                  {proxyBlocked ? (
                    <p id="ingest-studio-proxy-err" className="err ingest-studio-inline-err" role="alert">
                      {t('library.proxyUnavailable')}
                    </p>
                  ) : null}
                  {ingestLinkUrlLooksInvalid(importUrl) ? (
                    <p id="ingest-studio-link-err" className="err ingest-studio-inline-err" role="alert">
                      {t('ingest.linkUrlInvalid')}
                    </p>
                  ) : null}
                  <IngestExtraTagsMultiSelect
                    className="ingest-studio-card-tags"
                    catalog={userTags}
                    selected={linkExtraTags.tags}
                    disabled={busy}
                    onChange={linkExtraTags.setTags}
                  />
                  <AppSubmitButton
                    className="ingest-studio-foot-action w-full"
                    ready={!ingestSubmitDisabled}
                    busy={busy}
                    onClick={() => void importFromUrl()}
                  >
                    {studioLinkSubmit}
                  </AppSubmitButton>
                </div>
              </section>
            ) : null}
            <section
              className="ingest-studio-card ingest-studio-card-ingest ingest-studio-card-file"
              aria-labelledby="ingest-from-file-title"
            >
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
              <div className="ingest-studio-card-body ingest-studio-card-body-grow ingest-studio-card-ingest-body">
                {fileInput}
                <div className="ingest-studio-card-main-slot">
                  <IngestStudioIconHit
                    className="ingest-studio-main-hit h-full w-full"
                    icon={Upload}
                    disabled={busy}
                    ariaLabel={t('library.chooseFile')}
                    onClick={() => fileInputRef.current?.click()}
                  />
                </div>
              </div>
              <div className="ingest-studio-card-foot">
                <IngestExtraTagsMultiSelect
                  className="ingest-studio-card-tags"
                  catalog={userTags}
                  selected={fileExtraTags.tags}
                  disabled={busy}
                  onChange={fileExtraTags.setTags}
                />
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
            <section
              className="ingest-studio-card ingest-studio-card-ingest ingest-studio-card-mic"
              aria-labelledby="ingest-from-mic-title"
            >
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
              <div className="ingest-studio-card-body ingest-studio-card-body-grow ingest-studio-card-ingest-body">
                <div className="ingest-studio-card-main-slot">
                  <IngestStudioIconHit
                    className="ingest-studio-main-hit h-full w-full"
                    icon={MicIcon}
                    disabled={busy}
                    ariaLabel={t('library.recordMic')}
                    onClick={() => setRecordOpen(true)}
                  />
                </div>
              </div>
              <div className="ingest-studio-card-foot">
                <IngestExtraTagsMultiSelect
                  className="ingest-studio-card-tags"
                  catalog={userTags}
                  selected={micExtraTags.tags}
                  disabled={busy}
                  onChange={micExtraTags.setTags}
                />
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
                  <AppHoverHint content={ingestUrlHoverHint} side="bottom">
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
                  selected={linkExtraTags.tags}
                  disabled={busy}
                  onChange={linkExtraTags.setTags}
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
            <IngestExtraTagsMultiSelect
              catalog={userTags}
              selected={fileExtraTags.tags}
              disabled={busy}
              onChange={fileExtraTags.setTags}
            />
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
            <IngestExtraTagsMultiSelect
              catalog={userTags}
              selected={micExtraTags.tags}
              disabled={busy}
              onChange={micExtraTags.setTags}
            />
          </div>
          <IngestPipelinePanel />
        </CardContent>
      </Card>
      {micModal}
    </>
  )
}
