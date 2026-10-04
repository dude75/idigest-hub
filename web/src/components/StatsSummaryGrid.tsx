import { useTranslation } from 'react-i18next'
import { StatCard, StatGrid } from './StatCard'
import { formatDecimal, formatInteger, fmtMediaTime } from '../util'

type Props = {
  tasksTranscribe: number
  tasksSummarize: number
  audioSec: number
  summaryChars: number
  amount: string
  amountLabelKey: string
  amountTooltipKey: string
  tooltipPrefix?: 'stats' | 'instance'
}

export function StatsSummaryGrid({
  tasksTranscribe,
  tasksSummarize,
  audioSec,
  summaryChars,
  amount,
  amountLabelKey,
  amountTooltipKey,
  tooltipPrefix = 'stats',
}: Props) {
  const { t } = useTranslation()

  return (
    <StatGrid>
      <StatCard
        label={t('stats.statTranscribe')}
        title={t(`${tooltipPrefix}.transcribeDone`)}
        value={formatInteger(tasksTranscribe)}
        tone="transcribe"
      />
      <StatCard
        label={t('stats.statSummarize')}
        title={t(`${tooltipPrefix}.summarizeDone`)}
        value={formatInteger(tasksSummarize)}
        tone="summarize"
      />
      <StatCard
        label={t('stats.statAudio')}
        title={t(`${tooltipPrefix}.transcribedAudio`)}
        value={fmtMediaTime(audioSec)}
        tone="audio"
      />
      <StatCard
        label={t('stats.statChars')}
        title={t('stats.summaryChars')}
        value={formatInteger(summaryChars)}
        tone="chars"
      />
      <StatCard
        label={t(amountLabelKey)}
        title={t(amountTooltipKey)}
        value={formatDecimal(amount)}
        tone="amount"
      />
    </StatGrid>
  )
}
