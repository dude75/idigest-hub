import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { storeMfaChallengeId } from '../mfa'
import { resolveAuthContinuationPath } from '../routes'
import { showError } from '../util'

const SSO_ORG_ID_KEY = 'lastSsoOrgId'
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

type LoginMode = 'email' | 'sso'

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
  const initialMode: LoginMode = searchParams.get('mode') === 'sso' ? 'sso' : 'email'
  const [mode, setMode] = useState<LoginMode>(initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [orgId, setOrgId] = useState(readStoredOrgId)
  const [orgIdError, setOrgIdError] = useState('')
  const [busy, setBusy] = useState(false)

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />
  if (ready && me) {
    return <Navigate to={resolveAuthContinuationPath(me)} replace />
  }

  function switchMode(next: LoginMode) {
    setMode(next)
    setOrgIdError('')
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
      <div className="card auth-card stack">
        <h1>{t('auth.login')}</h1>

        <div className="auth-segment" role="tablist" aria-label={t('auth.login')}>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'email'}
            className={mode === 'email' ? 'active' : undefined}
            onClick={() => switchMode('email')}
          >
            {t('auth.modeEmail')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'sso'}
            className={mode === 'sso' ? 'active' : undefined}
            onClick={() => switchMode('sso')}
          >
            {t('auth.modeSso')}
          </button>
        </div>

        <div className="auth-panel-stack">
          <form
            className={`stack auth-panel${mode === 'email' ? '' : ' auth-panel-hidden'}`}
            aria-hidden={mode !== 'email'}
            inert={mode !== 'email' ? true : undefined}
            onSubmit={(e) => void onEmailSubmit(e)}
          >
            <label>
              {t('common.email')}
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              {t('common.password')}
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <button className="primary" disabled={busy} type="submit">{t('auth.login')}</button>
            <div className="stack">
              <Link to="/signup">{t('auth.toSignup')}</Link>
              <Link to="/forgot">{t('auth.toForgot')}</Link>
            </div>
          </form>
          <form
            className={`stack auth-panel${mode === 'sso' ? '' : ' auth-panel-hidden'}`}
            aria-hidden={mode !== 'sso'}
            inert={mode !== 'sso' ? true : undefined}
            onSubmit={onSsoSubmit}
          >
            <label>
              {t('auth.orgId')}
              <input
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
            </label>
            {orgIdError ? <p className="err">{orgIdError}</p> : <p className="muted">{t('auth.orgIdHint')}</p>}
            <button className="primary" type="submit">{t('sso.continue')}</button>
          </form>
        </div>
      </div>
    </AuthPageShell>
  )
}
