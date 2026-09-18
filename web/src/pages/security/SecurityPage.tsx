import { Navigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { isInstanceAdmin, useAuth } from '../../auth'
import { LIBRARY_DEFAULT } from '../../routes'
import { Tabs } from '../../components/Tabs'
import { AuditLogTab } from './AuditLogTab'
import { EncryptionTab } from './EncryptionTab'
import { SECURITY_TABS, resolveSecurityTab, type SecurityTab } from './constants'

function SecurityTabContent({ tab }: { tab: SecurityTab }) {
  switch (tab) {
    case 'audit':
      return <AuditLogTab />
    case 'encryption':
      return <EncryptionTab />
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
      <Tabs
        items={SECURITY_TABS.map((id) => ({
          id,
          label: t(`security.${id}`),
          active: tab === id,
          onClick: () => setTab(id),
        }))}
      />
      <SecurityTabContent tab={tab} />
    </div>
  )
}
