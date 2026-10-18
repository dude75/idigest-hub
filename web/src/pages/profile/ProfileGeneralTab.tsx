import { Card, CardContent } from '@/components/ui/card'
import { ProfileCardHeader } from './ProfileCardHeader'
import { AppInputField, AppSelectField } from '../../components/app/AppFormControls'
import { allowedDefaultRoutes, defaultRouteLabel, type DefaultRoute } from '../../routes'
import type { DateTimeFormatId } from '../../types'
import { DATE_TIME_FORMATS } from '../../util/datetimeFormat'
import { TIMEZONE_OPTIONS } from '../../util/timezones'
import { useProfilePage } from './ProfilePageContext'
import { ProfileSection, ProfileSectionDivider } from './ProfileSection'

export function ProfileGeneralTab() {
  const {
    t,
    me,
    firstName,
    setFirstNameLocal,
    lastName,
    setLastNameLocal,
    namesDirty,
    namesOk,
    saveProfileNames,
    defaultRoute,
    setDefaultRouteLocal,
    defaultRouteDirty,
    routeOk,
    saveDefaultRoute,
    dateTimeFormat,
    setDateTimeFormatLocal,
    timezone,
    setTimezoneLocal,
    dateTimePreview,
    dateTimeDirty,
    dateTimeOk,
    saveDateTimePrefs,
    setNamesOk,
    setRouteOk,
    setDateTimeOk,
  } = useProfilePage()

  return (
    <Card className="admin-form-card">
      <ProfileCardHeader title={t('profile.tabGeneral')} lead={t('profile.tabGeneralLead')} />
      <CardContent className="flex flex-col gap-6">
        <ProfileSection
          title={t('profile.names')}
          description={t('profile.namesHint')}
          saveReady={namesDirty}
          onSave={() => void saveProfileNames()}
          saved={namesOk}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <AppInputField
              label={t('common.firstName')}
              htmlFor="profile-first-name"
              value={firstName}
              onChange={(e) => {
                setNamesOk(false)
                setFirstNameLocal(e.target.value)
              }}
            />
            <AppInputField
              label={t('common.lastName')}
              htmlFor="profile-last-name"
              value={lastName}
              onChange={(e) => {
                setNamesOk(false)
                setLastNameLocal(e.target.value)
              }}
            />
          </div>
        </ProfileSection>

        <ProfileSectionDivider />

        <ProfileSection
          title={t('profile.defaultRoute')}
          description={t('profile.defaultRouteHint')}
          saveReady={defaultRouteDirty}
          onSave={() => void saveDefaultRoute()}
          saved={routeOk}
        >
          <AppSelectField
            label={t('profile.defaultRoute')}
            htmlFor="profile-default-route"
            value={defaultRoute}
            onValueChange={(route) => {
              setRouteOk(false)
              setDefaultRouteLocal(route as DefaultRoute)
            }}
            options={allowedDefaultRoutes(me).map((route) => ({
              value: route,
              label: defaultRouteLabel(route, t),
            }))}
          />
        </ProfileSection>

        <ProfileSectionDivider />

        <ProfileSection
          title={t('profile.dateTimeTitle')}
          description={t('profile.dateTimeHint')}
          saveReady={dateTimeDirty}
          onSave={() => void saveDateTimePrefs()}
          saved={dateTimeOk}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <AppSelectField
              label={t('profile.dateTimeFormat')}
              htmlFor="profile-dt-format"
              value={dateTimeFormat}
              onValueChange={(next) => {
                setDateTimeOk(false)
                setDateTimeFormatLocal(next as 'inherit' | DateTimeFormatId)
              }}
              options={[
                {
                  value: 'inherit',
                  label: t('profile.dateTimeInherit', {
                    value: t(`dateTime.format.${me?.date_time_prefs.instance_format ?? 'eu_24h'}`),
                  }),
                },
                ...DATE_TIME_FORMATS.map((id) => ({ value: id, label: t(`dateTime.format.${id}`) })),
              ]}
            />
            <AppSelectField
              label={t('profile.timezone')}
              htmlFor="profile-timezone"
              value={timezone}
              onValueChange={(next) => {
                setDateTimeOk(false)
                setTimezoneLocal(next)
              }}
              options={[
                {
                  value: 'inherit',
                  label: t('profile.dateTimeInherit', {
                    value: me?.date_time_prefs.instance_timezone ?? 'GMT+0',
                  }),
                },
                ...TIMEZONE_OPTIONS.map((tz) => ({ value: tz, label: tz })),
                ...(timezone !== 'inherit' &&
                !TIMEZONE_OPTIONS.includes(timezone as (typeof TIMEZONE_OPTIONS)[number])
                  ? [{ value: timezone, label: timezone }]
                  : []),
              ]}
            />
          </div>
          <p className="muted text-sm">{t('profile.dateTimePreview', { sample: dateTimePreview })}</p>
        </ProfileSection>
      </CardContent>
    </Card>
  )
}
