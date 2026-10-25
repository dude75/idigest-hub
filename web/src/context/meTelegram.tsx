import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '../api'
import { useAuth } from '../auth'
import type { SchemaMeTelegramStatusResponse } from '../openapi'

export type MeTelegramStatus = SchemaMeTelegramStatusResponse

const TELEGRAM_LINK_POLL_MS = 3000
const TELEGRAM_LINK_AWAITING_STORAGE_KEY = 'idigest:telegram-link-awaiting'

function readLinkAwaitingFromSession(): boolean {
  try {
    return sessionStorage.getItem(TELEGRAM_LINK_AWAITING_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function writeLinkAwaitingToSession(awaiting: boolean) {
  try {
    if (awaiting) sessionStorage.setItem(TELEGRAM_LINK_AWAITING_STORAGE_KEY, '1')
    else sessionStorage.removeItem(TELEGRAM_LINK_AWAITING_STORAGE_KEY)
  } catch {
    /* private mode / blocked storage */
  }
}

type MeTelegramContextValue = {
  status: MeTelegramStatus | null
  /** `null` until the first status fetch finishes. */
  linked: boolean | null
  refresh: (opts?: { toastOnLink?: boolean }) => Promise<MeTelegramStatus | null>
  setLinkAwaitingBot: (awaiting: boolean) => void
}

const MeTelegramCtx = createContext<MeTelegramContextValue | null>(null)

export function MeTelegramProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const member = Boolean(me?.org)
  const [status, setStatus] = useState<MeTelegramStatus | null>(null)
  const [linkAwaitingBot, setLinkAwaitingBotState] = useState(false)
  const linkedRef = useRef(false)

  const setLinkAwaitingBot = useCallback((awaiting: boolean) => {
    writeLinkAwaitingToSession(awaiting)
    setLinkAwaitingBotState(awaiting)
  }, [])

  const refresh = useCallback(
    async (opts?: { toastOnLink?: boolean }) => {
      if (!member) {
        setStatus(null)
        linkedRef.current = false
        return null
      }
      try {
        const data = await api<MeTelegramStatus>('/me/telegram')
        const wasLinked = linkedRef.current
        linkedRef.current = data.linked
        setStatus(data)
        if (data.linked) setLinkAwaitingBot(false)
        if (opts?.toastOnLink && !wasLinked && data.linked) {
          toast.success(t('profile.telegramLinked'))
        }
        return data
      } catch {
        setStatus(null)
        return null
      }
    },
    [member, setLinkAwaitingBot, t],
  )

  useEffect(() => {
    if (!member) {
      setStatus(null)
      setLinkAwaitingBot(false)
      linkedRef.current = false
      return
    }
    if (readLinkAwaitingFromSession()) setLinkAwaitingBotState(true)
    void refresh()
  }, [member, me?.user.shell_show_telegram_link, refresh, setLinkAwaitingBot])

  const awaitingBotLink = linkAwaitingBot && Boolean(status && !status.linked)

  useEffect(() => {
    if (!member) return
    const onFocus = () => void refresh(awaitingBotLink ? { toastOnLink: true } : undefined)
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [member, awaitingBotLink, refresh])

  useEffect(() => {
    if (!awaitingBotLink) return
    const interval = window.setInterval(() => void refresh({ toastOnLink: true }), TELEGRAM_LINK_POLL_MS)
    return () => window.clearInterval(interval)
  }, [awaitingBotLink, refresh])

  const linked = member ? (status === null ? null : status.linked) : null

  return (
    <MeTelegramCtx.Provider
      value={{
        status,
        linked,
        refresh,
        setLinkAwaitingBot,
      }}
    >
      {children}
    </MeTelegramCtx.Provider>
  )
}

export function useMeTelegram() {
  const ctx = useContext(MeTelegramCtx)
  if (!ctx) throw new Error('useMeTelegram must be used within MeTelegramProvider')
  return ctx
}
