import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth'
import { AdminPage } from '../components/AdminSection'
import { IngestPanel } from '../components/IngestPanel'

export function IngestPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const hasOrg = Boolean(me?.org)

  if (!hasOrg) {
    return <Navigate to={me?.user.is_instance_admin ? '/app/instance' : '/app/profile'} replace />
  }

  return (
    <AdminPage>
      <div className="ingest-page">
        <header className="ingest-page-hero">
          <p className="ingest-page-lead">{t('ingest.lead')}</p>
        </header>
        <IngestPanel layout="studio" />
      </div>
    </AdminPage>
  )
}
