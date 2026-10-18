import { Card, CardContent } from '@/components/ui/card'
import { ProfileCardHeader } from './ProfileCardHeader'
import { Button } from '@/components/ui/button'
import { AdminFormActions, AppSubmitButton } from '../../components/app/AdminUi'
import { AppInputField } from '../../components/app/AppFormControls'
import { MfaSetupPanel } from '../../components/MfaSetupPanel'
import { useProfilePage } from './ProfilePageContext'
import { ProfileSection, ProfileSectionDivider } from './ProfileSection'

export function ProfileSecurityTab() {
  const {
    t,
    me,
    refresh,
    showLocalAuth,
    disablePw,
    setDisablePw,
    disableCode,
    setDisableCode,
    mfaBusy,
    disableMfa,
    current,
    setCurrent,
    next,
    setNext,
    passwordReady,
    ok,
    changePw,
  } = useProfilePage()

  if (!showLocalAuth || !me) return null

  return (
    <Card className="admin-form-card">
      <ProfileCardHeader title={t('profile.tabSecurity')} lead={t('profile.tabSecurityLead')} />
      <CardContent className="flex flex-col gap-6">
        <ProfileSection title={t('mfa.title')} description={t('mfa.profileLead')}>
          {me.mfa_enabled ? (
            <form className="flex flex-col gap-3" onSubmit={(e) => void disableMfa(e)}>
              <p className="ok">{t('mfa.enabled')}</p>
              {me.mfa_required && <p className="muted text-sm">{t('mfa.requiredByOrg')}</p>}
              {!me.mfa_required && (
                <>
                  <AppInputField
                    label={t('common.password')}
                    htmlFor="profile-mfa-disable-pw"
                    type="password"
                    required
                    value={disablePw}
                    onChange={(e) => setDisablePw(e.target.value)}
                    autoComplete="current-password"
                  />
                  <AppInputField
                    label={t('mfa.codeOrRecovery')}
                    htmlFor="profile-mfa-disable-code"
                    type="text"
                    required
                    value={disableCode}
                    onChange={(e) => setDisableCode(e.target.value)}
                  />
                  <Button variant="destructive" disabled={mfaBusy} type="submit">
                    {t('mfa.disable')}
                  </Button>
                </>
              )}
            </form>
          ) : (
            <MfaSetupPanel onComplete={() => void refresh()} />
          )}
        </ProfileSection>

        <ProfileSectionDivider />

        <ProfileSection title={t('auth.changePassword')}>
          <form className="flex flex-col gap-3" onSubmit={(e) => void changePw(e)}>
            <AppInputField
              label={t('auth.currentPassword')}
              htmlFor="profile-current-pw"
              type="password"
              required
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              autoComplete="current-password"
            />
            <AppInputField
              label={t('auth.newPassword')}
              htmlFor="profile-new-pw"
              type="password"
              required
              minLength={8}
              value={next}
              onChange={(e) => setNext(e.target.value)}
              autoComplete="new-password"
            />
            <AdminFormActions className="profile-actions">
              <AppSubmitButton type="submit" ready={passwordReady}>
                {t('common.save')}
              </AppSubmitButton>
              {ok ? <p className="ok">{t('profile.saved')}</p> : null}
            </AdminFormActions>
          </form>
        </ProfileSection>
      </CardContent>
    </Card>
  )
}
