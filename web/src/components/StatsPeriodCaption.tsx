import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { detectDatePreset } from '../util/datePreset'

type Props = {
  fromDay: string
  toDay: string
}

const presetLabelKey = {
  '1': 'stats.today',
  '7': 'stats.days7',
  '30': 'stats.days30',
  month: 'stats.month',
  all: 'stats.allTime',
} as const

export function StatsPeriodCaption({ fromDay, toDay }: Props) {
  const { t } = useTranslation()
  const preset = useMemo(() => detectDatePreset(fromDay, toDay), [fromDay, toDay])

  if (preset) return t(presetLabelKey[preset])
  if (fromDay && toDay) return t('stats.periodRange', { from: fromDay, to: toDay })
  if (fromDay) return t('stats.periodFrom', { from: fromDay })
  if (toDay) return t('stats.periodTo', { to: toDay })
  return t('stats.allTime')
}
