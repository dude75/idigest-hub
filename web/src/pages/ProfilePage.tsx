import { useEffect, useMemo } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
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
import { ProfileUiTab } from './profile/ProfileUiTab'
import { PROFILE_TELEGRAM_SECTION_ID } from './profile/constants'

function ProfilePageTabs() {
  const { t, showModelsTab, showLocalAuth } = useProfilePage()
  const location = useLocation()
  const [search, setSearch] = useSearchParams()

  const tabItems = useMemo(() => {
    const items: { id: ProfileTab; label: string }[] = [{ id: 'general', label: t('profile.tabGeneral') }]
    if (showModelsTab) items.push({ id: 'models', label: t('profile.tabModels') })
    if (showLocalAuth) items.push({ id: 'security', label: t('profile.tabSecurity') })
    items.push({ id: 'data', label: t('profile.tabData') })
    items.push({ id: 'ui', label: t('profile.tabUi') })
    return items
  }, [t, showModelsTab, showLocalAuth])

  const requested = resolveProfileTab(search.get('tab'))
  const tab = tabItems.some((item) => item.id === requested) ? requested : 'general'

  useEffect(() => {
    if (location.hash !== `#${PROFILE_TELEGRAM_SECTION_ID}`) return
    if (search.get('tab')) {
      setSearch({}, { replace: true })
    }
  }, [location.hash, search, setSearch])

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
      <TabsContent value="ui">
        <ProfileUiTab />
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
