import { Navigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { isInstanceAdmin, useAuth } from '../../auth'
import { LIBRARY_DEFAULT } from '../../routes'
import { AuditLogTab } from './AuditLogTab'
import { SECURITY_TABS, resolveSecurityTab, type SecurityTab } from './constants'

function SecurityTabContent({ tab }: { tab: SecurityTab }) {
  switch (tab) {
    case 'audit':
      return <AuditLogTab />
  }
}

export function SecurityPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [search, setSearch] = useSearchParams()
  const tab = resolveSecurityTab(search.get('tab'))

  function setTab(id: SecurityTab) {
    setSearch(id === 'audit' ? {} : { tab: id }, { replace: true })
  }

  if (!isInstanceAdmin(me)) return <Navigate to={LIBRARY_DEFAULT} replace />

  return (
    <div>
      <h1>{t('security.title')}</h1>
      <div className="tabs">
        {SECURITY_TABS.map((id) => (
          <button key={id} type="button" className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
            {t(`security.${id}`)}
          </button>
        ))}
      </div>
      <SecurityTabContent tab={tab} />
    </div>
  )
}
