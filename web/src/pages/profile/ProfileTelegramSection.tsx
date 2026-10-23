import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { Button } from '@/components/ui/button'
import { showError } from '../../util'
import { formatDateTime } from '../../util/datetimeFormat'
import { ProfileSection } from './ProfileSection'

type MeTelegramStatus = {
  bot_enabled: boolean
  bot_username: string | null
  bot_url: string | null
  linked: boolean
  linked_at: string | null
}

type MeTelegramLink = {
  code: string
  expires_at: string
  start_command: string
  bot_username: string | null
  bot_url: string | null
}

export function ProfileTelegramSection() {
  const { t, i18n } = useTranslation()
  const { me } = useAuth()
  const [status, setStatus] = useState<MeTelegramStatus | null>(null)
  const [link, setLink] = useState<MeTelegramLink | null>(null)
  const [busy, setBusy] = useState(false)
  const orgReady = Boolean(me?.org)

  function formatWhen(iso: string) {
    if (!me) return iso
    return formatDateTime(iso, me.date_time_prefs, i18n.language)
  }

  const load = useCallback(async () => {
    if (!orgReady) return
    try {
      const data = await api<MeTelegramStatus>('/me/telegram')
      setStatus(data)
    } catch (e) {
      showError(e)
    }
  }, [orgReady])

  useEffect(() => {
    if (!orgReady) return
    void load()
  }, [load, orgReady])

  async function createLink() {
    setBusy(true)
    try {
      const data = await api<MeTelegramLink>('/me/telegram/link', { method: 'POST' })
      setLink(data)
      await load()
      toast.success(t('profile.telegramCodeOk'))
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  async function unlink() {
    setBusy(true)
    try {
      await api('/me/telegram', { method: 'DELETE' })
      setLink(null)
      await load()
      toast.success(t('profile.telegramUnlinked'))
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  if (!orgReady || !status) return null

  const botUsername = link?.bot_username ?? status.bot_username
  const botUrl = link?.bot_url ?? status.bot_url

  return (
    <ProfileSection title={t('profile.telegramTitle')} description={t('profile.telegramLead')}>
      {!status.bot_enabled ? <p className="muted text-sm">{t('profile.telegramBotDisabled')}</p> : null}
      {status.bot_enabled && !botUsername ? (
        <p className="muted text-sm">{t('profile.telegramBotUsernamePending')}</p>
      ) : null}
      {botUsername && botUrl ? (
        <p className="text-sm">
          {t('profile.telegramBotLabel')}{' '}
          <a href={botUrl} target="_blank" rel="noreferrer">
            @{botUsername}
          </a>
        </p>
      ) : null}
      {status.linked ? (
        <div className="flex flex-col gap-2">
          <p className="ok text-sm">{t('profile.telegramLinked')}</p>
          {status.linked_at ? (
            <p className="muted text-sm">
              {t('profile.telegramLinkedAt')} {formatWhen(status.linked_at)}
            </p>
          ) : null}
          <Button type="button" variant="outline" disabled={busy} onClick={() => void unlink()}>
            {t('profile.telegramUnlink')}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <Button type="button" disabled={busy || !status.bot_enabled} onClick={() => void createLink()}>
            {t('profile.telegramGetCode')}
          </Button>
          {link ? (
            <div className="rounded-md border border-border p-3 text-sm flex flex-col gap-2">
              {botUrl ? (
                <p>
                  {t('profile.telegramOpenBot')}{' '}
                  <a href={botUrl} target="_blank" rel="noreferrer">
                    @{botUsername}
                  </a>
                </p>
              ) : null}
              <p className="font-medium">{t('profile.telegramCodeLabel')}</p>
              <p>
                <code>{link.start_command}</code>
              </p>
              <p className="muted">
                {t('profile.telegramCodeExpires')} {formatWhen(link.expires_at)}
              </p>
            </div>
          ) : null}
        </div>
      )}
    </ProfileSection>
  )
}
