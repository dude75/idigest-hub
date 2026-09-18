import { useTranslation } from 'react-i18next'
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
        <label>
          {t('stats.from')}
          <input type="date" value={fromDay} onChange={(e) => onFromChange(e.target.value)} />
        </label>
        <label>
          {t('stats.to')}
          <input type="date" value={toDay} onChange={(e) => onToChange(e.target.value)} />
        </label>
        {showOrgFilter ? (
          <label>
            {t('instance.orgs')}
            <select
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
            </select>
          </label>
        ) : null}
        <label>
          {t('stats.user')}
          <select
            value={userId}
            disabled={showOrgFilter && !orgId}
            onChange={(e) => onUserIdChange(e.target.value)}
          >
            <option value="">{t('common.all')}</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.email}</option>
            ))}
          </select>
        </label>
        <label>
          {t('stats.kind')}
          <select value={kind} onChange={(e) => onKindChange(e.target.value)}>
            <option value="">{t('common.all')}</option>
            <option value="transcribe">{t('task.type.transcribe')}</option>
            <option value="summarize">{t('task.type.summarize')}</option>
          </select>
        </label>
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

  return (
    <div className="card stack stats-filters">
      <div className="stats-section-head">
        <h2>{t('stats.filters')}</h2>
      </div>
      {fields}
    </div>
  )
}
