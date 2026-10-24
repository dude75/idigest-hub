import { useLayoutEffect, useState } from 'react'
import { MicIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useMeTelegram } from '../context/meTelegram'
import { PROFILE_TELEGRAM_SECTION_ID } from '../shell/constants'
import { shellShowsTelegramPrompt } from '../shell/telegramPrompt'
import { MicrophoneRecordModal } from './MicrophoneRecordModal'
import { AppHoverHint } from './app/AppHoverHint'
import { TelegramIcon } from './TelegramIcon'
import { loadIngestExtraTags, saveIngestExtraTags } from '../ingestExtraTags'
import { uploadMicrophoneRecording } from '../util/microphoneUpload'
import { showError } from '../util'
import { Button } from '@/components/ui/button'

/** Global mic entry (Shell); library ingest mic is unchanged. */
export function GlobalMicRecordAccess() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const { status } = useMeTelegram()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const showMicButton = Boolean(me?.org) && (me?.user.shell_show_mic ?? true)
  const showTelegramLink = shellShowsTelegramPrompt(me, status)
  const showShellActions = showMicButton || showTelegramLink

  useLayoutEffect(() => {
    if (!showShellActions) return

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
  }, [showShellActions])

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

  if (!showShellActions) {
    return null
  }

  return (
    <>
      <div className="shell-global-mic">
        <div className="shell-global-mic-stack">
          {showMicButton ? (
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
          ) : null}
          {showTelegramLink ? (
            <AppHoverHint content={t('shell.telegramLinkHint')}>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="shrink-0 bg-card text-[#2CA5E0] shadow-xs hover:text-[#229ED9]"
                aria-label={t('shell.telegramLinkHint')}
                onClick={() =>
                  nav({ pathname: '/app/profile', hash: `#${PROFILE_TELEGRAM_SECTION_ID}` })
                }
              >
                <TelegramIcon className="size-4" />
              </Button>
            </AppHoverHint>
          ) : null}
        </div>
      </div>
      {open && showMicButton ? (
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
