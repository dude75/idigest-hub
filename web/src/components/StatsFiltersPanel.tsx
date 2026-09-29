import { useTranslation } from 'react-i18next'
import { AppStackCard } from './AdminSection'
import { AppDateField, AppSelectField } from './app/AppFormControls'
import { DatePresetBar } from './DatePresetBar'

type UserOption = { id: string; email: string }
type OrgOption = { id: string; name: string }

type Props = {
  fromDay: string
  toDay: string
  onFromChange: (value: string) => void
  onToChange: (value: string) => void
  userId: string
  onUserIdChange: (value: string) => void
  users: UserOption[]
  kind: string
  onKindChange: (value: string) => void
  orgId?: string
  onOrgIdChange?: (value: string) => void
  orgs?: OrgOption[]
  embedded?: boolean
}

export function StatsFiltersPanel({
  fromDay,
  toDay,
  onFromChange,
  onToChange,
  userId,
  onUserIdChange,
  users,
  kind,
  onKindChange,
  orgId,
  onOrgIdChange,
  orgs,
  embedded = false,
}: Props) {
  const { t } = useTranslation()
  const showOrgFilter = orgs !== undefined && onOrgIdChange !== undefined

  const fields = (
    <>
      <div className="stats-filters-fields">
        <AppDateField
          label={t('stats.from')}
          htmlFor="stats-filter-from"
          value={fromDay}
          onChange={onFromChange}
        />
        <AppDateField
          label={t('stats.to')}
          htmlFor="stats-filter-to"
          value={toDay}
          onChange={onToChange}
        />
        {showOrgFilter ? (
          <AppSelectField
            label={t('instance.orgs')}
            htmlFor="stats-filter-org"
            value={orgId ?? ''}
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
        ) : null}
        <AppSelectField
          label={t('stats.user')}
          htmlFor="stats-filter-user"
          value={userId}
          disabled={showOrgFilter && !orgId}
          onChange={(e) => onUserIdChange(e.target.value)}
        >
          <option value="">{t('common.all')}</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>{u.email}</option>
          ))}
        </AppSelectField>
        <AppSelectField
          label={t('stats.kind')}
          htmlFor="stats-filter-kind"
          value={kind}
          onChange={(e) => onKindChange(e.target.value)}
        >
          <option value="">{t('common.all')}</option>
          <option value="transcribe">{t('task.type.transcribe')}</option>
          <option value="summarize">{t('task.type.summarize')}</option>
        </AppSelectField>
      </div>
      <DatePresetBar
        fromDay={fromDay}
        toDay={toDay}
        presets={['7', '30', 'month', 'all']}
        onFromChange={onFromChange}
        onToChange={onToChange}
      />
    </>
  )

  if (embedded) {
    return <section className="stack stats-filters-embedded">{fields}</section>
  }

  return <AppStackCard title={t('stats.filters')}>{fields}</AppStackCard>
}
