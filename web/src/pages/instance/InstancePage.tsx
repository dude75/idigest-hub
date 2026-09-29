import { lazy, Suspense } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { isInstanceAdmin, useAuth } from '../../auth'
import { LIBRARY_DEFAULT } from '../../routes'
import { INSTANCE_TABS, resolveInstanceTab, type InstanceTab } from './constants'
import { Tabs } from '../../components/Tabs'

const InstanceStatsTab = lazy(() =>
  import('./InstanceStatsTab').then((m) => ({ default: m.InstanceStatsTab })),
)
const InstanceWorkersTab = lazy(() =>
  import('./InstanceWorkersTab').then((m) => ({ default: m.InstanceWorkersTab })),
)
const InstanceTariffsTab = lazy(() =>
  import('./InstanceTariffsTab').then((m) => ({ default: m.InstanceTariffsTab })),
)
const InstanceOrgsTab = lazy(() =>
  import('./InstanceOrgsTab').then((m) => ({ default: m.InstanceOrgsTab })),
)
const InstanceLegalDocumentsTab = lazy(() =>
  import('./InstanceLegalDocumentsTab').then((m) => ({ default: m.InstanceLegalDocumentsTab })),
)
const InstanceSettingsTab = lazy(() =>
  import('./InstanceSettingsTab').then((m) => ({ default: m.InstanceSettingsTab })),
)
const InstanceBaseSkillsTab = lazy(() =>
  import('./InstanceBaseSkillsTab').then((m) => ({ default: m.InstanceBaseSkillsTab })),
)

function InstanceTabContent({ tab }: { tab: InstanceTab }) {
  switch (tab) {
    case 'stats':
      return <InstanceStatsTab />
    case 'workers':
      return <InstanceWorkersTab />
    case 'tariffs':
      return <InstanceTariffsTab />
    case 'orgs':
      return <InstanceOrgsTab />
    case 'legalDocuments':
      return <InstanceLegalDocumentsTab />
    case 'settings':
      return <InstanceSettingsTab />
    case 'baseSkills':
      return <InstanceBaseSkillsTab />
  }
}

export function InstancePage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [search, setSearch] = useSearchParams()
  const tab = resolveInstanceTab(search.get('tab'))

  function setTab(id: string) {
    const next = id as InstanceTab
    if (!INSTANCE_TABS.includes(next)) return
    setSearch(next === 'stats' ? {} : { tab: next }, { replace: true })
  }

  if (!isInstanceAdmin(me)) return <Navigate to={LIBRARY_DEFAULT} replace />

  const tabItems = INSTANCE_TABS.map((id) => ({
    id,
    label: t(`instance.${id}`),
    active: tab === id,
    onClick: () => setTab(id),
  }))

  return (
    <div className="instance-admin">
      <Tabs items={tabItems} ariaLabel={t('instance.title')} />
      <Suspense fallback={<p className="muted">{t('common.loading')}</p>}>
        <InstanceTabContent tab={tab} />
      </Suspense>
    </div>
  )
}
