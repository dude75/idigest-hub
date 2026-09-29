import { useRef, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthCard } from '../components/auth/AuthCard'
import { AuthPageShell } from '../components/AuthPageShell'
import { AppSubmitButton } from '@/components/app/AdminUi'
import { FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { storeMfaChallengeId } from '../mfa'
import { resolveAuthContinuationPath } from '../routes'
import { showError } from '../util'

const SSO_ORG_ID_KEY = 'lastSsoOrgId'
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function readStoredOrgId(): string {
  try {
    return localStorage.getItem(SSO_ORG_ID_KEY) || ''
  } catch {
    return ''
  }
}

export function LoginPage() {
  const { t } = useTranslation()
  const { ready, bootstrapDone, me, refresh } = useAuth()
  const nav = useNavigate()
  const [searchParams] = useSearchParams()
  const defaultSso = searchParams.get('mode') === 'sso'
  const emailPanelRef = useRef<HTMLFormElement>(null)
  const ssoPanelRef = useRef<HTMLFormElement>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [orgId, setOrgId] = useState(readStoredOrgId)
  const [orgIdError, setOrgIdError] = useState('')
  const [busy, setBusy] = useState(false)

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />
  if (ready && me) {
    return <Navigate to={resolveAuthContinuationPath(me)} replace />
  }

  function syncPanelA11y(emailActive: boolean) {
    emailPanelRef.current?.setAttribute('aria-hidden', emailActive ? 'false' : 'true')
    ssoPanelRef.current?.setAttribute('aria-hidden', emailActive ? 'true' : 'false')
  }

  function onModeInputChange(e: FormEvent<HTMLDivElement>) {
    const target = e.target
    if (!(target instanceof HTMLInputElement) || target.name !== 'login-mode') return
    syncPanelA11y(target.value === 'email')
  }

  async function onEmailSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const result = await api<{ status: string; challenge_id?: string }>(
        '/auth/login',
        { method: 'POST', body: JSON.stringify({ email, password }) },
      )
      if (result.status === 'mfa_required' && result.challenge_id) {
        storeMfaChallengeId(result.challenge_id)
        nav('/verify-2fa', { replace: true })
        return
      }
      const profile = await refresh()
      nav(resolveAuthContinuationPath(profile), { replace: true })
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  function onSsoSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = orgId.trim()
    if (!UUID_RE.test(trimmed)) {
      setOrgIdError(t('auth.orgIdInvalid'))
      return
    }
    setOrgIdError('')
    try {
      localStorage.setItem(SSO_ORG_ID_KEY, trimmed)
    } catch {
      /* ignore */
    }
    nav(`/sso/${trimmed}`, { replace: true })
  }

  return (
    <AuthPageShell>
      <AuthCard title={t('auth.login')}>
          <div className="login-mode" onChange={onModeInputChange}>
            <input
              type="radio"
              name="login-mode"
              id="login-mode-email"
              value="email"
              className="login-mode-input"
              defaultChecked={!defaultSso}
            />
            <input
              type="radio"
              name="login-mode"
              id="login-mode-sso"
              value="sso"
              className="login-mode-input"
              defaultChecked={defaultSso}
            />

            <div className="auth-segment login-mode-tabs" role="tablist" aria-label={t('auth.login')}>
              <label htmlFor="login-mode-email" className="login-mode-tab" role="tab">
                {t('auth.modeEmail')}
              </label>
              <label htmlFor="login-mode-sso" className="login-mode-tab" role="tab">
                {t('auth.modeSso')}
              </label>
            </div>

            <div className="auth-panel-stack login-mode-panels">
              <form
                ref={emailPanelRef}
                className="auth-panel login-panel-email flex flex-col gap-4"
                aria-hidden={defaultSso ? 'true' : 'false'}
                onSubmit={(e) => void onEmailSubmit(e)}
              >
                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <FieldLabel htmlFor="login-email">{t('common.email')}</FieldLabel>
                    <Input
                      id="login-email"
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <FieldLabel htmlFor="login-password">{t('common.password')}</FieldLabel>
                    <Input
                      id="login-password"
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                </div>
                <AppSubmitButton
                  className="w-full"
                  type="submit"
                  ready={Boolean(email.trim() && password.length > 0)}
                  busy={busy}
                >
                  {t('auth.login')}
                </AppSubmitButton>
                <div className="flex min-h-[2.75rem] flex-col gap-1 text-sm">
                  <Link to="/signup">{t('auth.toSignup')}</Link>
                  <Link to="/forgot">{t('auth.toForgot')}</Link>
                </div>
              </form>

              <form
                ref={ssoPanelRef}
                className="auth-panel login-panel-sso flex flex-col gap-4"
                aria-hidden={defaultSso ? 'false' : 'true'}
                onSubmit={onSsoSubmit}
              >
                <div className="flex flex-col gap-2">
                  <FieldLabel htmlFor="login-org-id">{t('auth.orgId')}</FieldLabel>
                  <Input
                    id="login-org-id"
                    type="text"
                    required
                    value={orgId}
                    spellCheck={false}
                    autoComplete="off"
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    aria-invalid={orgIdError ? true : undefined}
                    onChange={(e) => {
                      setOrgId(e.target.value)
                      if (orgIdError) setOrgIdError('')
                    }}
                  />
                  {orgIdError ? (
                    <FieldError>{orgIdError}</FieldError>
                  ) : (
                    <FieldDescription>{t('auth.orgIdHint')}</FieldDescription>
                  )}
                </div>
                <AppSubmitButton className="w-full" type="submit" ready={orgId.trim().length > 0}>
                  {t('sso.continue')}
                </AppSubmitButton>
                <div className="min-h-[2.75rem]" aria-hidden />
              </form>
            </div>
          </div>
      </AuthCard>
    </AuthPageShell>
  )
}
