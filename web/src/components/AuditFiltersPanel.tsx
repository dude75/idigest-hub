import { useTranslation } from 'react-i18next'
import { AppStackCard } from './AdminSection'
import { AppDateField, AppSelectField } from './app/AppFormControls'
import { DatePresetBar } from './DatePresetBar'

export const AUDIT_ACTIONS = [
  'instance.setup',
  'tariff.create',
  'tariff.update',
  'tariff.archive',
  'tariff.unarchive',
  'wallet.delta',
  'user.password_reset',
  'org.tariff',
  'org.tariff.self',
  'org.sso.update',
  'impersonate.start',
  'impersonate.stop',
  'user.disable',
  'user.enable',
  'user.offboard.transfer',
  'user.offboard.wipe',
  'user.account.delete',
  'audio.wipe',
  'transcript.wipe',
  'transcript.rename',
  'summary.update',
  'summary.delete',
  'summary.public_link.create',
  'summary.public_link.revoke',
  'summary.public_link.view',
  'org.public_links_policy',
  'org.delete',
] as const

type UserOption = { id: string; email: string }
type OrgOption = { id: string; name: string }

type Props = {
  fromDay: string
  toDay: string
  onFromChange: (value: string) => void
  onToChange: (value: string) => void
  orgId: string
  onOrgIdChange: (value: string) => void
  orgs: OrgOption[]
  userId: string
  onUserIdChange: (value: string) => void
  users: UserOption[]
  action: string
  onActionChange: (value: string) => void
}

export function auditActionLabel(action: string, t: (key: string, opts?: { defaultValue?: string }) => string): string {
  return t(`audit.actions.${action.replace(/\./g, '_')}`, { defaultValue: action })
}

export function AuditFiltersPanel({
  fromDay,
  toDay,
  onFromChange,
  onToChange,
  orgId,
  onOrgIdChange,
  orgs,
  userId,
  onUserIdChange,
  users,
  action,
  onActionChange,
}: Props) {
  const { t } = useTranslation()

  return (
    <AppStackCard title={t('stats.filters')}>
      <div className="stats-filters-fields">
        <AppDateField
          label={t('stats.from')}
          htmlFor="audit-filter-from"
          value={fromDay}
          onChange={onFromChange}
        />
        <AppDateField
          label={t('stats.to')}
          htmlFor="audit-filter-to"
          value={toDay}
          onChange={onToChange}
        />
        <AppSelectField
          label={t('instance.orgs')}
          htmlFor="audit-filter-org"
          value={orgId}
          onChange={(e) => {
            onOrgIdChange(e.target.value)
            onUserIdChange('')
          }}
        >
          <option value="">{t('common.all')}</option>
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>{o.name}</option>
          ))}
        </AppSelectField>
        <AppSelectField
          label={t('stats.user')}
          htmlFor="audit-filter-user"
          value={userId}
          disabled={!orgId}
          onChange={(e) => onUserIdChange(e.target.value)}
        >
          <option value="">{t('common.all')}</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>{u.email}</option>
          ))}
        </AppSelectField>
        <AppSelectField
          label={t('audit.action')}
          htmlFor="audit-filter-action"
          value={action}
          onChange={(e) => onActionChange(e.target.value)}
        >
          <option value="">{t('common.all')}</option>
          {AUDIT_ACTIONS.map((a) => (
            <option key={a} value={a}>{auditActionLabel(a, t)}</option>
          ))}
        </AppSelectField>
      </div>
      <DatePresetBar
        fromDay={fromDay}
        toDay={toDay}
        presets={['1', '7', '30', 'month']}
        onFromChange={onFromChange}
        onToChange={onToChange}
      />
    </AppStackCard>
  )
}
