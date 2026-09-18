import { useEffect, useState } from 'react'
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { resolveAuthContinuationPath } from '../routes'
import { errorText, showError } from '../util'

type SsoInfo = {
  org_id: string
  org_name: string
  configured: boolean
  enabled: boolean
  login_url: string | null
}

export function SsoLoginPage() {
  const { orgId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const { t } = useTranslation()
  const { ready, bootstrapDone, me } = useAuth()
  const [info, setInfo] = useState<SsoInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const authError = searchParams.get('error')

  useEffect(() => {
    if (!orgId) return
    setLoading(true)
    api<SsoInfo>(`/auth/sso/${orgId}/info`)
      .then(setInfo)
      .catch(showError)
      .finally(() => setLoading(false))
  }, [orgId])

  if (ready && !bootstrapDone) return <Navigate to="/setup" replace />
  if (ready && me) return <Navigate to={resolveAuthContinuationPath(me)} replace />
  if (!orgId) return <Navigate to="/login" replace />

  function startSso() {
    window.location.href = `/api/v1/auth/sso/${orgId}/start`
  }

  return (
    <AuthPageShell>
      <div className="card auth-card stack">
        <h1>{t('sso.title')}</h1>
        {authError && <p className="err">{errorText(new ApiError(authError, ''), t)}</p>}
        {loading && <p className="muted">{t('common.loading')}</p>}
        {!loading && info && (
          <>
            <p>{info.org_name}</p>
            {!info.configured && <p className="err">{t('sso.notConfigured')}</p>}
            {info.configured && !info.enabled && <p className="err">{t('sso.notEnabled')}</p>}
            {info.configured && info.enabled && (
              <button className="primary" type="button" onClick={startSso}>
                {t('sso.continue')}
              </button>
            )}
          </>
        )}
        <Link to="/login?mode=sso">{t('auth.changeOrgId')}</Link>
        <Link to="/login">{t('auth.toEmailLogin')}</Link>
      </div>
    </AuthPageShell>
  )
}
