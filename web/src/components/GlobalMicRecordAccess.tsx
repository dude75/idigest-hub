import { useLayoutEffect, useState } from 'react'
import { MicIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { api, apiUpload } from '../api'
import { useAuth } from '../auth'
import { MIC_RECORDING_TAG } from '../constants/userTags'
import { MicrophoneRecordModal } from './MicrophoneRecordModal'
import { AppHoverHint } from './app/AppHoverHint'
import {
  beginPipelineRun,
  endPipelineRun,
  pipelineNavState,
  pipelineShouldTranscribe,
  transcribeRequest,
} from '../pipeline'
import { libraryPath } from '../routes'
import type { Audio, Task, UserTag } from '../types'
import { showError } from '../util'
import { Button } from '@/components/ui/button'

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

/** Global mic entry (Shell); library ingest mic is unchanged. */
export function GlobalMicRecordAccess() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const showMic = Boolean(me?.org)

  useLayoutEffect(() => {
    if (!showMic) return

    const shell = document.querySelector('.app-shell')
    const topbar = document.querySelector('.app-shell > .topbar')
    const page = document.querySelector('.app-shell > .page')
    const banner = document.querySelector('.app-shell > .banner')
    if (!(shell instanceof HTMLElement) || !(topbar instanceof HTMLElement)) return

    const sync = () => {
      const pagePadTop = page ? Number.parseFloat(getComputedStyle(page).paddingTop) || 0 : 16
      const top = topbar.getBoundingClientRect().bottom + pagePadTop
      shell.style.setProperty('--shell-mic-top', `${top}px`)
    }

    sync()
    const ro = new ResizeObserver(sync)
    ro.observe(topbar)
    if (banner instanceof HTMLElement) ro.observe(banner)
    window.addEventListener('resize', sync)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', sync)
    }
  }, [showMic])

  async function uploadFromMic(file: File) {
    const pipeline = beginPipelineRun()
    setBusy(true)
    try {
      const body = new FormData()
      body.append('file', file)
      body.append('from_microphone', 'true')
      const item = await apiUpload<Audio>('/audios', body)
      try {
        item.user_tags = await tagMicrophoneRecording(item.id)
      } catch (e) {
        showError(e)
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
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  if (!showMic) {
    return null
  }

  return (
    <>
      <div className="shell-global-mic">
        <AppHoverHint content={t('library.recordMic')}>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="shrink-0 bg-card text-destructive shadow-xs hover:text-destructive"
            disabled={busy}
            aria-label={t('library.recordMic')}
            onClick={() => setOpen(true)}
          >
            <MicIcon className="size-4 text-destructive" aria-hidden="true" />
          </Button>
        </AppHoverHint>
      </div>
      {open ? (
        <MicrophoneRecordModal
          busy={busy}
          onClose={() => setOpen(false)}
          onSave={(file) => {
            setOpen(false)
            void uploadFromMic(file)
          }}
        />
      ) : null}
    </>
  )
}
