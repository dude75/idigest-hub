import { useTranslation } from 'react-i18next'
import { AppStackCard } from './AdminSection'
import { AppDateField, AppSelectField } from './app/AppFormControls'
import { allOption } from './app/selectOptions'
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
            onValueChange={(next) => {
              onOrgIdChange(next)
              onUserIdChange('')
            }}
            options={[allOption(t('common.all')), ...orgs.map((o) => ({ value: o.id, label: o.name }))]}
          />
        ) : null}
        <AppSelectField
          label={t('stats.user')}
          htmlFor="stats-filter-user"
          value={userId}
          disabled={showOrgFilter && !orgId}
          onValueChange={onUserIdChange}
          options={[allOption(t('common.all')), ...users.map((u) => ({ value: u.id, label: u.email }))]}
        />
        <AppSelectField
          label={t('stats.kind')}
          htmlFor="stats-filter-kind"
          value={kind}
          onValueChange={onKindChange}
          options={[
            allOption(t('common.all')),
            { value: 'transcribe', label: t('task.type.transcribe') },
            { value: 'summarize', label: t('task.type.summarize') },
          ]}
        />
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
