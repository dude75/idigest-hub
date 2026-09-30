import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Mic, PauseIcon, PlayIcon, XIcon } from 'lucide-react'
import { Modal } from './Modal'
import { MicrophoneLevelVisualizer } from './MicrophoneLevelVisualizer'
import { AppSelect } from './app/AppSelect'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AppSubmitButton } from './app/AdminUi'
import { cn } from '@/lib/utils'
import {
  detachMediaRecorder,
  listAudioInputDevices,
  mediaBlobToRecordingFile,
  mediaStreamStopTracks,
  MIN_RECORDING_UPLOAD_BYTES,
  pickMediaRecorderMimeType,
  waitForMediaRecorderStop,
} from '../util/microphoneRecord'
import { showError } from '../util'

type Props = {
  onClose: () => void
  onSave: (file: File) => void
  busy?: boolean
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function MicrophoneRecordModal({ onClose, onSave, busy }: Props) {
  const { t } = useTranslation()
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [deviceId, setDeviceId] = useState('default')
  const [recording, setRecording] = useState(false)
  const [paused, setPaused] = useState(false)
  const [starting, setStarting] = useState(true)
  const [switchingDevice, setSwitchingDevice] = useState(false)
  const [durationSec, setDurationSec] = useState(0)
  const [hasAudio, setHasAudio] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deviceRestartNote, setDeviceRestartNote] = useState(false)
  const [captureStream, setCaptureStream] = useState<MediaStream | null>(null)

  const streamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const captureGenerationRef = useRef(0)
  const timerRef = useRef<number | null>(null)
  const durationRef = useRef(0)
  const mimeTypeRef = useRef<string | undefined>(undefined)

  const clearTimer = useCallback(() => {
    if (timerRef.current != null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const startDurationTimer = useCallback(() => {
    clearTimer()
    timerRef.current = window.setInterval(() => {
      durationRef.current += 1
      setDurationSec(durationRef.current)
    }, 1000)
  }, [clearTimer])

  const releaseCapture = useCallback(
    async (opts: { discardChunks: boolean }) => {
      clearTimer()
      const rec = recorderRef.current
      recorderRef.current = null
      captureGenerationRef.current += 1

      if (rec) {
        detachMediaRecorder(rec)
        if (rec.state !== 'inactive') {
          try {
            await waitForMediaRecorderStop(rec)
          } catch {
            /* drop broken session */
          }
        }
      }

      if (opts.discardChunks) {
        chunksRef.current = []
        setHasAudio(false)
      }

      mediaStreamStopTracks(streamRef.current)
      streamRef.current = null
      setCaptureStream(null)
      setRecording(false)
      setPaused(false)
    },
    [clearTimer],
  )

  const pauseCapture = useCallback(() => {
    const rec = recorderRef.current
    if (!rec || rec.state !== 'recording') return
    clearTimer()
    try {
      rec.pause()
      setRecording(false)
      setPaused(true)
    } catch (e) {
      showError(e)
    }
  }, [clearTimer])

  const resumeCapture = useCallback(() => {
    const rec = recorderRef.current
    if (!rec || rec.state !== 'paused') return
    try {
      rec.resume()
      setPaused(false)
      setRecording(true)
      startDurationTimer()
    } catch (e) {
      showError(e)
    }
  }, [startDurationTimer])

  const startCapture = useCallback(
    async (selectedDeviceId: string) => {
      if (!navigator.mediaDevices?.getUserMedia) {
        showError(new Error(t('library.recordUnsupported')))
        onClose()
        return
      }
      const mime = pickMediaRecorderMimeType()
      if (!mime) {
        showError(new Error(t('library.recordUnsupported')))
        onClose()
        return
      }

      await releaseCapture({ discardChunks: true })
      mimeTypeRef.current = mime
      durationRef.current = 0
      setDurationSec(0)
      setStarting(true)

      const generation = captureGenerationRef.current

      try {
        const audioConstraints: MediaTrackConstraints =
          selectedDeviceId && selectedDeviceId !== 'default'
            ? { deviceId: { exact: selectedDeviceId } }
            : {}
        const stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints })
        if (generation !== captureGenerationRef.current) {
          mediaStreamStopTracks(stream)
          return
        }

        streamRef.current = stream
        setCaptureStream(stream)

        const recorder = new MediaRecorder(stream, { mimeType: mime })
        recorderRef.current = recorder
        recorder.ondataavailable = (e) => {
          if (generation !== captureGenerationRef.current) return
          if (e.data.size > 0) {
            chunksRef.current.push(e.data)
            setHasAudio(true)
          }
        }
        recorder.onerror = () => {
          if (generation !== captureGenerationRef.current) return
          showError(new Error(t('library.recordFailed')))
        }
        recorder.start(1000)
        setRecording(true)
        setPaused(false)
        setStarting(false)
        startDurationTimer()

        const inputs = await listAudioInputDevices()
        setDevices(inputs)
      } catch (e) {
        setStarting(false)
        showError(e)
        onClose()
      }
    },
    [onClose, releaseCapture, startDurationTimer, t],
  )

  useEffect(() => {
    void startCapture(deviceId)
    return () => {
      void releaseCapture({ discardChunks: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial mount only
  }, [])

  async function handleDeviceChange(nextId: string) {
    if (nextId === deviceId || switchingDevice || saving) return
    setDeviceId(nextId)
    setDeviceRestartNote(true)
    setSwitchingDevice(true)
    try {
      await startCapture(nextId)
    } finally {
      setSwitchingDevice(false)
    }
  }

  async function finalizeRecordingBlob(): Promise<Blob> {
    const mime = mimeTypeRef.current || 'audio/webm'
    const rec = recorderRef.current
    recorderRef.current = null
    captureGenerationRef.current += 1

    if (rec) {
      detachMediaRecorder(rec)
      if (rec.state !== 'inactive') {
        await waitForMediaRecorderStop(rec)
      }
    }

    return new Blob(chunksRef.current, { type: mime })
  }

  async function handleSave() {
    if ((!hasAudio && !recording) || saving || busy || starting || switchingDevice) return
    setSaving(true)
    setRecording(false)
    setPaused(false)
    clearTimer()
    try {
      const blob = await finalizeRecordingBlob()
      mediaStreamStopTracks(streamRef.current)
      streamRef.current = null
      setCaptureStream(null)

      if (blob.size < MIN_RECORDING_UPLOAD_BYTES) {
        showError(new Error(t('library.recordTooShort')))
        setSaving(false)
        await startCapture(deviceId)
        return
      }

      const mime = mimeTypeRef.current || blob.type || 'audio/webm'
      onSave(mediaBlobToRecordingFile(blob, mime))
    } catch (e) {
      showError(e)
      setSaving(false)
      await startCapture(deviceId)
    }
  }

  function handleClose() {
    void releaseCapture({ discardChunks: true })
    onClose()
  }

  const vizMode = starting || switchingDevice
    ? 'starting'
    : recording
      ? 'recording'
      : paused
        ? 'paused'
        : 'idle'

  const statusLabel =
    starting || switchingDevice
      ? t('library.recordStarting')
      : recording
        ? t('library.recordStatusActive')
        : paused
          ? t('library.recordStatusPaused')
          : ''

  const deviceOptions = [
    { value: 'default', label: t('library.recordDefaultMic') },
    ...devices.map((d) => ({
      value: d.deviceId,
      label: d.label || t('library.recordMicUnnamed', { id: d.deviceId.slice(0, 8) }),
    })),
  ]

  const transportDisabled = saving || Boolean(busy) || starting || switchingDevice

  const transportToggleLabel = recording ? t('library.recordStop') : t('library.recordResume')
  const canToggleFromPanel =
    (recording || paused) && !starting && !switchingDevice && !saving && !busy

  const toggleRecordingTransport = () => {
    if (!canToggleFromPanel) return
    if (recording) pauseCapture()
    else resumeCapture()
  }

  const transportActions = (
    <>
      <Button type="button" variant="outline" size="sm" disabled={busy || saving} onClick={handleClose}>
        {t('common.cancel')}
      </Button>
      {recording || paused ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={transportDisabled}
          className="gap-1.5 px-2.5"
          onClick={() => toggleRecordingTransport()}
        >
          {recording ? (
            <PauseIcon className="size-4 shrink-0" aria-hidden="true" />
          ) : (
            <PlayIcon className="size-4 shrink-0" aria-hidden="true" />
          )}
          <span className="truncate">{transportToggleLabel}</span>
        </Button>
      ) : null}
      <AppSubmitButton
        size="sm"
        className="shrink-0"
        ready={(hasAudio || recording || paused) && !starting && !switchingDevice}
        busy={saving || Boolean(busy)}
        onClick={() => void handleSave()}
      >
        {t('library.recordSave')}
      </AppSubmitButton>
    </>
  )

  return (
    <Modal
      title={t('library.recordTitle')}
      description={t('library.recordHint')}
      onClose={handleClose}
      closeOnBackdrop={!recording && !paused}
      panelClassName="mic-record-modal sm:max-w-xl font-sans bg-gradient-to-t from-primary/5 to-card shadow-xs dark:bg-card dark:bg-none"
    >
      <div className="flex min-w-0 flex-col gap-4">
        <div
          role={canToggleFromPanel ? 'button' : undefined}
          tabIndex={canToggleFromPanel ? 0 : undefined}
          aria-label={
            canToggleFromPanel
              ? recording
                ? t('library.recordStop')
                : t('library.recordResume')
              : undefined
          }
          onClick={() => toggleRecordingTransport()}
          onKeyDown={(event) => {
            if (!canToggleFromPanel) return
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              toggleRecordingTransport()
            }
          }}
          className={cn(
            'mic-record-panel flex w-full min-w-0 flex-col items-center gap-3 overflow-hidden rounded-xl border bg-card px-4 py-5 shadow-xs outline-none',
            recording && 'mic-record-panel--recording',
            paused && 'mic-record-panel--paused',
            (starting || switchingDevice) && 'mic-record-panel--starting',
            canToggleFromPanel &&
              'cursor-pointer transition-colors hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          )}
        >
          <MicrophoneLevelVisualizer stream={captureStream} mode={vizMode} className="w-full" />
          <div className="flex min-h-[4.75rem] flex-col items-center justify-center gap-1" aria-live="polite">
            <span className="font-mono text-3xl font-medium tabular-nums tracking-tight">
              {starting || switchingDevice ? '—:——' : formatDuration(durationSec)}
            </span>
            <span
              className={cn(
                'inline-flex h-5 min-w-[10.5rem] items-center justify-center gap-2 text-sm font-medium',
                !statusLabel && 'invisible',
                recording && 'text-red-600 dark:text-red-400',
                paused && 'text-amber-700 dark:text-amber-400',
                (starting || switchingDevice) && 'text-muted-foreground',
              )}
            >
              <span
                className={cn(
                  'size-2 shrink-0 rounded-full',
                  recording && 'animate-pulse bg-red-500',
                  paused && 'bg-amber-500',
                  (starting || switchingDevice) && 'animate-pulse bg-muted-foreground/50',
                  !statusLabel && 'bg-transparent',
                )}
                aria-hidden="true"
              />
              {statusLabel || t('library.recordStatusActive')}
            </span>
          </div>
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex min-w-0 items-center gap-2">
            <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
              <Label
                htmlFor="record-mic-select"
                className="flex shrink-0 cursor-default items-center p-0 font-normal"
              >
                <Mic className="size-5 text-muted-foreground" aria-hidden />
                <span className="sr-only">{t('library.recordMicLabel')}</span>
              </Label>
              <AppSelect
                id="record-mic-select"
                size="sm"
                className="max-w-[10rem]"
                expandMenu
                disabled={starting || saving || Boolean(busy) || switchingDevice}
                value={deviceId}
                onValueChange={(v) => void handleDeviceChange(v || 'default')}
                options={deviceOptions}
              />
            </div>
            <div className="flex shrink-0 items-center gap-1.5">{transportActions}</div>
          </div>
          <div className="flex min-h-6 items-center justify-center" aria-live="polite">
            <Badge
              variant="outline"
              className={cn(
                'h-6 max-w-full gap-1 pr-1 pl-2 font-normal',
                'border-red-200/90 bg-red-50 text-red-700 dark:border-red-800/70 dark:bg-red-950/40 dark:text-red-300',
                !deviceRestartNote && 'pointer-events-none invisible',
              )}
            >
              <span className="max-w-[min(100%,20rem)] truncate">{t('library.recordMicChanged')}</span>
              <button
                type="button"
                aria-label={t('common.close')}
                className={cn(
                  'inline-flex shrink-0 items-center justify-center rounded-sm border-0 bg-transparent p-0',
                  'text-red-600/70 hover:text-red-800 dark:text-red-300/80 dark:hover:text-red-200',
                )}
                onClick={(event) => {
                  event.preventDefault()
                  event.stopPropagation()
                  setDeviceRestartNote(false)
                }}
              >
                <XIcon className="size-3" data-icon="inline-end" strokeWidth={2} aria-hidden />
              </button>
            </Badge>
          </div>
        </div>
      </div>
    </Modal>
  )
}
