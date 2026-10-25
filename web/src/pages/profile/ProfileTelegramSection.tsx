import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { useMeTelegram } from '../../context/meTelegram'
import type { SchemaMeTelegramLinkResponse } from '../../openapi'
import { Button } from '@/components/ui/button'
import { showError } from '../../util'
import { formatDateTime } from '../../util/datetimeFormat'
import { AppUrlCopyRow } from '../../components/app/AppUrlCopyRow'
import { PROFILE_TELEGRAM_SECTION_ID } from '../../shell/constants'
import { ProfileSection } from './ProfileSection'
import { useProfileHashScroll } from './useProfileHashScroll'

export function ProfileTelegramSection() {
  const { t, i18n } = useTranslation()
  const { me } = useAuth()
  const { status, refresh, setLinkAwaitingBot } = useMeTelegram()
  const [link, setLink] = useState<SchemaMeTelegramLinkResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const orgReady = Boolean(me?.org)

  useProfileHashScroll(PROFILE_TELEGRAM_SECTION_ID, orgReady, status)

  useEffect(() => {
    if (status?.linked) setLink(null)
  }, [status?.linked])

  useEffect(() => {
    if (!status?.bot_username || !link?.bot_username) return
    if (status.bot_username !== link.bot_username) setLink(null)
  }, [status?.bot_username, link?.bot_username])

  function formatWhen(iso: string) {
    if (!me) return iso
    return formatDateTime(iso, me.date_time_prefs, i18n.language)
  }

  async function createLink() {
    setBusy(true)
    try {
      const data = await api<SchemaMeTelegramLinkResponse>('/me/telegram/link', { method: 'POST' })
      setLink(data)
      setLinkAwaitingBot(true)
      await refresh()
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
      setLinkAwaitingBot(false)
      await refresh()
      toast.success(t('profile.telegramUnlinked'))
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  if (!orgReady) return null

  const botUsername = status?.bot_username ?? link?.bot_username
  const botUrl =
    status?.bot_url ?? link?.bot_url ?? (botUsername ? `https://t.me/${botUsername}` : null)

  return (
    <ProfileSection
      headingId={PROFILE_TELEGRAM_SECTION_ID}
      title={t('profile.telegramTitle')}
      description={t('profile.telegramLead')}
    >
      {!status ? null : (
        <>
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
                  <AppUrlCopyRow value={link.start_command} className="public-link-url-row-compact" />
                  <p className="muted">
                    {t('profile.telegramCodeExpires')} {formatWhen(link.expires_at)}
                  </p>
                </div>
              ) : null}
            </div>
          )}
        </>
      )}
    </ProfileSection>
  )
}
