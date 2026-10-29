import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { useMeTelegram } from '../../context/meTelegram'
import { AppCheckboxRow } from '../../components/app/AppFormControls'
import { showError } from '../../util'
import { appMutedText } from '../../components/app/appTypography'

export function ProfileShellPrefsSection() {
  const { t } = useTranslation()
  const { me, refresh } = useAuth()
  const { linked: telegramLinked } = useMeTelegram()
  const [busy, setBusy] = useState(false)

  if (!me?.org) return null

  const showMic = me.user.shell_show_mic ?? true
  const showTelegramLink = me.user.shell_show_telegram_link ?? true
  const telegramLinkLocked = telegramLinked === true
  const telegramPrefsReady = telegramLinked !== null

  async function patchShellPrefs(patch: { shell_show_mic?: boolean; shell_show_telegram_link?: boolean }) {
    setBusy(true)
    try {
      await api('/me', { method: 'PATCH', body: JSON.stringify(patch) })
      await refresh()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <AppCheckboxRow
        id="profile-shell-show-mic"
        label={t('profile.shellShowMic')}
        checked={showMic}
        disabled={busy}
        onCheckedChange={(checked) => void patchShellPrefs({ shell_show_mic: checked })}
      />
      <p className={appMutedText}>{t('profile.shellShowMicHint')}</p>
      {telegramPrefsReady ? (
        <>
          <AppCheckboxRow
            id="profile-shell-show-telegram-link"
            label={t('profile.shellShowTelegramLink')}
            checked={telegramLinkLocked ? false : showTelegramLink}
            disabled={busy || telegramLinkLocked}
            onCheckedChange={(checked) => void patchShellPrefs({ shell_show_telegram_link: checked })}
          />
          <p className={appMutedText}>
            {telegramLinkLocked
              ? t('profile.shellShowTelegramLinkLinkedHint')
              : t('profile.shellShowTelegramLinkHint')}
          </p>
        </>
      ) : null}
    </div>
  )
}
