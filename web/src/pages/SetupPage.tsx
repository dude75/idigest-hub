import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthCard } from '../components/auth/AuthCard'
import { AuthField } from '../components/auth/AuthField'
import { AppSelect } from '../components/app/AppSelect'
import { AuthPageShell } from '../components/AuthPageShell'
import { LanguageSwitcher } from '../components/LanguageSwitcher'
import { LOCALES } from '../i18n'
import type { Locale } from '../types'
import { showError } from '../util'
import { AppSubmitButton } from '@/components/app/AdminUi'
import { Input } from '@/components/ui/input'

export function SetupPage() {
  const { t, i18n } = useTranslation()
  const { ready, bootstrapDone, refresh } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)

  if (ready && bootstrapDone) return <Navigate to="/login" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      await api('/setup', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          bootstrap_token: token,
          locale: i18n.language,
        }),
      })
      await refresh()
      nav('/app', { replace: true })
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthPageShell>
      <AuthCard
        title={
          <span className="flex w-full items-center justify-between gap-2">
            <span>{t('auth.setup')}</span>
            <LanguageSwitcher />
          </span>
        }
      >
        <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
          <AuthField label={t('common.email')} htmlFor="setup-email">
            <Input
              id="setup-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </AuthField>
          <AuthField label={t('common.password')} htmlFor="setup-password">
            <Input
              id="setup-password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </AuthField>
          <AuthField label={t('auth.bootstrapToken')} htmlFor="setup-token">
            <Input id="setup-token" required value={token} onChange={(e) => setToken(e.target.value)} />
          </AuthField>
          <AuthField label="Locale" htmlFor="setup-locale">
            <AppSelect
              id="setup-locale"
              value={i18n.language}
              onValueChange={(l) => void i18n.changeLanguage(l as Locale)}
              options={LOCALES.map((l) => ({ value: l, label: t(`lang.${l}`) }))}
            />
          </AuthField>
          <AppSubmitButton
            className="w-full"
            type="submit"
            ready={Boolean(email.trim() && password.length >= 8 && token.trim())}
            busy={busy}
          >
            {t('common.save')}
          </AppSubmitButton>
        </form>
      </AuthCard>
    </AuthPageShell>
  )
}
