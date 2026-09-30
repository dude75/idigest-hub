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
import { AppStackCard } from './AdminSection'
import {
  AdminDataTable,
  AdminTableHeadHint,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  adminTableCellNum,
  adminTableHeadNum,
} from './app/AdminDataTable'
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
            <XAxis dataKey="label" tick={{ fontSize: 12 }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={36} />
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
            <XAxis dataKey="label" tick={{ fontSize: 12 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 12 }} width={48} tickFormatter={(v) => fmtMediaTime(Number(v))} />
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
            <XAxis dataKey="label" tick={{ fontSize: 12 }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={48} tickFormatter={(v) => formatInteger(Number(v))} />
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
            <XAxis dataKey="label" tick={{ fontSize: 12 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 12 }} width={48} />
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
    <AppStackCard
      title={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>{t('stats.calendar')}</span>
          <Segmented
            variant="pill"
            value={view}
            options={viewOptions}
            onChange={setView}
            ariaLabel={t('stats.viewMode')}
          />
        </div>
      }
    >
      {days.length === 0 ? (
        <p className="stats-empty">{t('common.empty')}</p>
      ) : view === 'table' ? (
        <AdminDataTable>
          <TableHeader>
            <TableRow>
              <TableHead>{t('stats.day')}</TableHead>
              <AdminTableHeadHint className={adminTableHeadNum} hint={t('stats.transcribeDone')}>
                {t('stats.statTranscribe')}
              </AdminTableHeadHint>
              <AdminTableHeadHint className={adminTableHeadNum} hint={t('stats.summarizeDone')}>
                {t('stats.statSummarize')}
              </AdminTableHeadHint>
              <AdminTableHeadHint className={adminTableHeadNum} hint={t('stats.transcribedAudio')}>
                {t('stats.statAudio')}
              </AdminTableHeadHint>
              <AdminTableHeadHint className={adminTableHeadNum} hint={t('stats.summaryChars')}>
                {t('stats.statChars')}
              </AdminTableHeadHint>
              <AdminTableHeadHint className={adminTableHeadNum} hint={t(amountTooltipKey)}>
                {t(amountLabelKey)}
              </AdminTableHeadHint>
            </TableRow>
          </TableHeader>
          <TableBody>
            {days.map((day) => (
              <TableRow key={day.date}>
                <TableCell className="tabular-nums">{day.date}</TableCell>
                <TableCell className={adminTableCellNum}>{formatInteger(day.tasks_transcribe_success)}</TableCell>
                <TableCell className={adminTableCellNum}>{formatInteger(day.tasks_summarize_success)}</TableCell>
                <TableCell className={adminTableCellNum}>{fmtMediaTime(day.audio_transcribed_sec)}</TableCell>
                <TableCell className={adminTableCellNum}>{formatInteger(day.summary_chars)}</TableCell>
                <TableCell className={adminTableCellNum}>{formatDecimal(day.amount)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </AdminDataTable>
      ) : (
        <StatsDaysCharts days={chartDays} amountLabelKey={amountLabelKey} />
      )}
    </AppStackCard>
  )
}
