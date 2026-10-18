import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { userDisplayName, userInitials } from '../../userDisplay'
import { useProfilePage } from './ProfilePageContext'

type MetricTone = 'default' | 'ok' | 'danger' | 'muted'

function ProfileMetric({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value: string
  tone?: MetricTone
}) {
  return (
    <div className="min-w-0 flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <span
        className={cn(
          'truncate text-sm font-semibold leading-tight',
          tone === 'ok' && 'text-[var(--ok)]',
          tone === 'danger' && 'text-destructive',
          tone === 'muted' && 'text-muted-foreground',
        )}
      >
        {value}
      </span>
    </div>
  )
}

export function ProfileHeader() {
  const { t, me, orgLabel, mfaSummary, activeTokens, apiAllowed, formatInteger } = useProfilePage()

  if (!me) return null

  const displayName = userDisplayName(me.user)
  const emailLine = me.user.email?.trim() || ''

  const mfaTone: MetricTone =
    mfaSummary.tone === 'proxy-up' ? 'ok' : mfaSummary.tone === 'proxy-down' ? 'danger' : 'muted'
  const apiTone: MetricTone = apiAllowed ? 'ok' : 'muted'

  return (
    <Card className="profile-identity font-sans bg-gradient-to-t from-primary/5 to-card shadow-xs dark:bg-card dark:bg-none">
      <CardContent className="flex flex-col gap-4 pt-6">
        <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center">
          <div
            className="flex size-14 shrink-0 items-center justify-center rounded-full bg-primary/10 text-base font-semibold text-primary"
            aria-hidden
          >
            {userInitials(me.user)}
          </div>
          <div className="min-w-0 flex-1 space-y-1">
            <h1 className="min-w-0 break-all text-xl font-semibold leading-snug tracking-tight">
              {displayName}
            </h1>
            {emailLine ? <p className="break-all text-sm text-muted-foreground">{emailLine}</p> : null}
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-4">
          <ProfileMetric label={t('profile.kpiOrg')} value={orgLabel} />
          <ProfileMetric label={t('profile.kpiMfa')} value={mfaSummary.label} tone={mfaTone} />
          <ProfileMetric
            label={t('profile.kpiTokens')}
            value={formatInteger(activeTokens.length)}
          />
          <ProfileMetric
            label={t('profile.kpiApi')}
            value={apiAllowed ? t('profile.apiOn') : t('profile.apiOff')}
            tone={apiTone}
          />
        </div>
      </CardContent>
    </Card>
  )
}
