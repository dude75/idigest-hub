import { lazy, Suspense } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { isInstanceAdmin, useAuth } from '../../auth'
import { LIBRARY_DEFAULT } from '../../routes'
import { INSTANCE_TABS, resolveInstanceTab, type InstanceTab } from './constants'

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

  function setTab(id: InstanceTab) {
    setSearch(id === 'stats' ? {} : { tab: id }, { replace: true })
  }

  if (!isInstanceAdmin(me)) return <Navigate to={LIBRARY_DEFAULT} replace />

  return (
    <div>
      <h1>{t('instance.title')}</h1>
      <div className="tabs">
        {INSTANCE_TABS.map((id) => (
          <button key={id} type="button" className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
            {t(`instance.${id}`)}
          </button>
        ))}
      </div>
      <Suspense fallback={<p className="muted">{t('common.loading')}</p>}>
        <InstanceTabContent tab={tab} />
      </Suspense>
    </div>
  )
}
