import { useEffect, useState } from 'react'
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import { AuthCard } from '../components/auth/AuthCard'
import { AuthPageShell } from '../components/AuthPageShell'
import { resolveAuthContinuationPath } from '../routes'
import { errorText, showError } from '../util'
import { Button } from '@/components/ui/button'

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
      <AuthCard title={t('sso.title')}>
        <div className="space-y-4">
          {authError && <p className="err text-sm">{errorText(new ApiError(authError, ''), t)}</p>}
          {loading && <p className="text-sm text-muted-foreground">{t('common.loading')}</p>}
          {!loading && info && (
            <>
              <p>{info.org_name}</p>
              {!info.configured && <p className="err text-sm">{t('sso.notConfigured')}</p>}
              {info.configured && !info.enabled && <p className="err text-sm">{t('sso.notEnabled')}</p>}
              {info.configured && info.enabled && (
                <Button className="w-full" type="button" onClick={startSso}>
                  {t('sso.continue')}
                </Button>
              )}
            </>
          )}
          <Link to="/login?mode=sso" className="block text-sm">
            {t('auth.changeOrgId')}
          </Link>
          <Link to="/login" className="block text-sm">
            {t('auth.toEmailLogin')}
          </Link>
        </div>
      </AuthCard>
    </AuthPageShell>
  )
}
