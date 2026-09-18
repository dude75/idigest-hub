import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { OrgStatsDay } from '../types'
import { formatDecimal, formatInteger, fmtMediaTime } from '../util'
import { Segmented } from './Segmented'
import { STATS_CHART_COLORS, type StatsChartMetric } from './statsTheme'

type ViewMode = 'table' | 'chart'

type ChartDay = OrgStatsDay & {
  label: string
  amountNum: number
}

type Props = {
  days: OrgStatsDay[]
  amountLabelKey?: string
  amountTooltipKey?: string
}

function chartClass(metric: StatsChartMetric): string {
  return `stats-chart stats-chart-${metric}`
}

function StatsDaysCharts({
  days,
  amountLabelKey,
}: {
  days: ChartDay[]
  amountLabelKey: string
}) {
  const { t } = useTranslation()

  return (
    <div className="stats-charts">
      <div className={chartClass('transcribe')}>
        <h3 className="stats-chart-title">{t('stats.chartTasks')}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={days} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={36} />
            <Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''} />
            <Legend />
            <Bar dataKey="tasks_transcribe_success" name={t('stats.statTranscribe')} fill={STATS_CHART_COLORS.transcribe} />
            <Bar dataKey="tasks_summarize_success" name={t('stats.statSummarize')} fill={STATS_CHART_COLORS.summarize} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className={chartClass('audio')}>
        <h3 className="stats-chart-title">{t('stats.statAudio')}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={days} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} width={48} tickFormatter={(v) => fmtMediaTime(Number(v))} />
            <Tooltip
              labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
              formatter={(value) => fmtMediaTime(Number(value))}
            />
            <Line
              type="monotone"
              dataKey="audio_transcribed_sec"
              name={t('stats.statAudio')}
              stroke={STATS_CHART_COLORS.audio}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className={chartClass('chars')}>
        <h3 className="stats-chart-title">{t('stats.statChars')}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={days} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={48} tickFormatter={(v) => formatInteger(Number(v))} />
            <Tooltip
              labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
              formatter={(value) => formatInteger(Number(value))}
            />
            <Line
              type="monotone"
              dataKey="summary_chars"
              name={t('stats.statChars')}
              stroke={STATS_CHART_COLORS.chars}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className={chartClass('amount')}>
        <h3 className="stats-chart-title">{t(amountLabelKey)}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={days} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip
              labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
              formatter={(value) => [formatDecimal(Number(value)), t(amountLabelKey)]}
            />
            <Bar dataKey="amountNum" name={t(amountLabelKey)} fill={STATS_CHART_COLORS.amount} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function StatsDaysView({
  days,
  amountLabelKey = 'stats.statSpent',
  amountTooltipKey = 'stats.spent',
}: Props) {
  const { t } = useTranslation()
  const [view, setView] = useState<ViewMode>('table')

  const chartDays = useMemo(
    () => days.map((day) => ({
      ...day,
      label: day.date.slice(5),
      amountNum: Number(day.amount) || 0,
    })),
    [days],
  )

  const viewOptions = useMemo(
    () => [
      { value: 'table' as const, label: t('stats.viewTable') },
      { value: 'chart' as const, label: t('stats.viewChart') },
    ],
    [t],
  )

  return (
    <div className="card stack stats-days-panel">
      <div className="stats-days-head">
        <h2>{t('stats.calendar')}</h2>
        <Segmented
          variant="pill"
          value={view}
          options={viewOptions}
          onChange={setView}
          ariaLabel={t('stats.viewMode')}
        />
      </div>
      {days.length === 0 ? (
        <p className="stats-empty">{t('common.empty')}</p>
      ) : view === 'table' ? (
        <div className="stats-table-wrap">
          <table className="stats-table">
            <thead>
              <tr>
                <th>{t('stats.day')}</th>
                <th className="num" title={t('stats.transcribeDone')}>{t('stats.statTranscribe')}</th>
                <th className="num" title={t('stats.summarizeDone')}>{t('stats.statSummarize')}</th>
                <th className="num" title={t('stats.transcribedAudio')}>{t('stats.statAudio')}</th>
                <th className="num" title={t('stats.summaryChars')}>{t('stats.statChars')}</th>
                <th className="num" title={t(amountTooltipKey)}>{t(amountLabelKey)}</th>
              </tr>
            </thead>
            <tbody>
              {days.map((day) => (
                <tr key={day.date}>
                  <td className="stats-day">{day.date}</td>
                  <td className="num">{formatInteger(day.tasks_transcribe_success)}</td>
                  <td className="num">{formatInteger(day.tasks_summarize_success)}</td>
                  <td className="num">{fmtMediaTime(day.audio_transcribed_sec)}</td>
                  <td className="num">{formatInteger(day.summary_chars)}</td>
                  <td className="num">{formatDecimal(day.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <StatsDaysCharts days={chartDays} amountLabelKey={amountLabelKey} />
      )}
    </div>
  )
}
