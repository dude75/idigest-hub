import { Card, CardContent } from '@/components/ui/card'
import { appMutedText } from '@/components/app/appTypography'
import { ProfileCardHeader } from './ProfileCardHeader'
import { useProfilePage } from './ProfilePageContext'
import { ProfileShellPrefsSection } from './ProfileShellPrefsSection'

export function ProfileUiTab() {
  const { t, me } = useProfilePage()

  return (
    <Card className="admin-form-card">
      <ProfileCardHeader title={t('profile.tabUi')} lead={t('profile.tabUiLead')} />
      <CardContent className="flex flex-col gap-6">
        {me?.org ? (
          <ProfileShellPrefsSection />
        ) : (
          <p className={appMutedText}>{t('profile.tabUiOrgRequired')}</p>
        )}
      </CardContent>
    </Card>
  )
}
