import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from '../components/Tabs'
import { AdminPage } from '../components/AdminSection'
import { PROFILE_TABS, resolveProfileTab, type ProfileTab } from './profile/constants'
import { ProfileDataTab } from './profile/ProfileDataTab'
import { ProfileDeleteModal } from './profile/ProfileDeleteModal'
import { ProfileGeneralTab } from './profile/ProfileGeneralTab'
import { ProfileHeader } from './profile/ProfileHeader'
import { ProfileModelsTab } from './profile/ProfileModelsTab'
import { ProfilePageProvider, useProfilePage } from './profile/ProfilePageContext'
import { ProfileSecurityTab } from './profile/ProfileSecurityTab'

function ProfilePageTabs() {
  const { t, showModelsTab, showLocalAuth } = useProfilePage()
  const [search, setSearch] = useSearchParams()

  const tabItems = useMemo(() => {
    const items: { id: ProfileTab; label: string }[] = [{ id: 'general', label: t('profile.tabGeneral') }]
    if (showModelsTab) items.push({ id: 'models', label: t('profile.tabModels') })
    if (showLocalAuth) items.push({ id: 'security', label: t('profile.tabSecurity') })
    items.push({ id: 'data', label: t('profile.tabData') })
    return items
  }, [t, showModelsTab, showLocalAuth])

  const requested = resolveProfileTab(search.get('tab'))
  const tab = tabItems.some((item) => item.id === requested) ? requested : 'general'

  function setTab(id: ProfileTab) {
    setSearch(id === 'general' ? {} : { tab: id }, { replace: true })
  }

  return (
    <TabsRoot
      value={tab}
      onValueChange={(value) => {
        if ((PROFILE_TABS as readonly string[]).includes(value)) setTab(value as ProfileTab)
      }}
      className="profile-tabs mb-4 w-full gap-4"
    >
      <TabsList aria-label={t('profile.title')} className="w-full flex-wrap sm:w-fit">
        {tabItems.map((item) => (
          <TabsTrigger key={item.id} value={item.id}>
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="general">
        <ProfileGeneralTab />
      </TabsContent>
      {showModelsTab && (
        <TabsContent value="models">
          <ProfileModelsTab />
        </TabsContent>
      )}
      {showLocalAuth && (
        <TabsContent value="security">
          <ProfileSecurityTab />
        </TabsContent>
      )}
      <TabsContent value="data">
        <ProfileDataTab />
      </TabsContent>
    </TabsRoot>
  )
}

export function ProfilePage() {
  return (
    <ProfilePageProvider>
      <AdminPage>
        <ProfileHeader />
        <ProfilePageTabs />
        <ProfileDeleteModal />
      </AdminPage>
    </ProfilePageProvider>
  )
}
