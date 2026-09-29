import { useState, type FormEvent } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthCard } from '../components/auth/AuthCard'
import { AuthField } from '../components/auth/AuthField'
import { AuthPageShell } from '../components/AuthPageShell'
import { showError } from '../util'
import { AppSubmitButton } from '@/components/app/AdminUi'
import { Input } from '@/components/ui/input'

export function ResetPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone } = useAuth()
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [password, setPassword] = useState('')
  const [ok, setOk] = useState(false)
  const [busy, setBusy] = useState(false)

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      await api('/auth/password/reset/confirm', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: password }),
      })
      setOk(true)
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthPageShell>
      <AuthCard title={t('auth.reset')}>
        {ok ? (
          <div className="space-y-4">
            <p className="ok text-sm">{t('auth.resetDone')}</p>
            <Link to="/login" className="text-sm">
              {t('auth.login')}
            </Link>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
            <AuthField label={t('auth.newPassword')} htmlFor="reset-password">
              <Input
                id="reset-password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </AuthField>
            <AppSubmitButton
              className="w-full"
              type="submit"
              ready={Boolean(token && password.length >= 8)}
              busy={busy}
            >
              {t('common.save')}
            </AppSubmitButton>
          </form>
        )}
      </AuthCard>
    </AuthPageShell>
  )
}
