import { useLayoutEffect, useState } from 'react'
import { MicIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { MicrophoneRecordModal } from './MicrophoneRecordModal'
import { AppHoverHint } from './app/AppHoverHint'
import { loadIngestExtraTags, saveIngestExtraTags } from '../ingestExtraTags'
import { uploadMicrophoneRecording } from '../util/microphoneUpload'
import { showError } from '../util'
import { Button } from '@/components/ui/button'

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
    setBusy(true)
    try {
      await uploadMicrophoneRecording(
        file,
        nav,
        { clearExtraTags: () => saveIngestExtraTags('mic', []) },
        me,
        loadIngestExtraTags('mic'),
      )
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
            className="shrink-0 bg-card text-emerald-600/80 shadow-xs hover:text-emerald-700"
            disabled={busy}
            aria-label={t('library.recordMic')}
            onClick={() => setOpen(true)}
          >
            <MicIcon className="size-4" aria-hidden="true" />
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
