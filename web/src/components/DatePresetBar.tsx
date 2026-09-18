import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { datePreset } from '../util/date'
import { detectDatePreset, type DatePresetId } from '../util/datePreset'
import { Segmented } from './Segmented'

type Props = {
  fromDay: string
  toDay: string
  presets: DatePresetId[]
  onFromChange: (value: string) => void
  onToChange: (value: string) => void
}

const presetDays: Record<DatePresetId, number | 'month' | 'all'> = {
  '1': 1,
  '7': 7,
  '30': 30,
  month: 'month',
  all: 'all',
}

export function DatePresetBar({ fromDay, toDay, presets, onFromChange, onToChange }: Props) {
  const { t } = useTranslation()
  const active = useMemo(() => detectDatePreset(fromDay, toDay), [fromDay, toDay])

  const labels: Record<DatePresetId, string> = {
    '1': t('stats.today'),
    '7': t('stats.days7'),
    '30': t('stats.days30'),
    month: t('stats.month'),
    all: t('stats.allTime'),
  }

  const options = presets.map((id) => ({ value: id, label: labels[id] }))
  const value = active && presets.includes(active) ? active : null

  return (
    <Segmented
      variant="pill"
      value={value}
      options={options}
      onChange={(id) => datePreset(presetDays[id], onFromChange, onToChange)}
    />
  )
}
