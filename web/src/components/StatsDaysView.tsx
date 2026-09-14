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
import { formatAudioTime } from '../util'

type ViewMode = 'table' | 'chart'

const CHART_COLORS = {
  transcribe: '#2563eb',
  summarize: '#067647',
  amount: '#9333ea',
  audio: '#2563eb',
  chars: '#067647',
}

type ChartDay = OrgStatsDay & {
  label: string
  amountNum: number
}

function StatsDaysCharts({ days }: { days: ChartDay[] }) {
  const { t } = useTranslation()

  return (
    <div className="stats-charts">
      <div className="stats-chart">
        <h3 className="stats-chart-title">{t('stats.chartTasks')}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={days} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={36} />
            <Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''} />
            <Legend />
            <Bar dataKey="tasks_transcribe_success" name={t('task.type.transcribe')} fill={CHART_COLORS.transcribe} />
            <Bar dataKey="tasks_summarize_success" name={t('task.type.summarize')} fill={CHART_COLORS.summarize} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="stats-chart">
        <h3 className="stats-chart-title">{t('stats.transcribedAudio')}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={days} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} width={48} tickFormatter={(v) => `${Math.round(v / 60)}m`} />
            <Tooltip
              labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
              formatter={(value) => formatAudioTime(Number(value), t)}
            />
            <Line type="monotone" dataKey="audio_transcribed_sec" name={t('stats.transcribedAudio')} stroke={CHART_COLORS.audio} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="stats-chart">
        <h3 className="stats-chart-title">{t('stats.summaryChars')}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={days} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={48} />
            <Tooltip labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''} />
            <Line type="monotone" dataKey="summary_chars" name={t('stats.summaryChars')} stroke={CHART_COLORS.chars} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="stats-chart">
        <h3 className="stats-chart-title">{t('stats.spent')}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={days} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip
              labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ''}
              formatter={(value) => [Number(value).toFixed(2), t('stats.spent')]}
            />
            <Bar dataKey="amountNum" name={t('stats.spent')} fill={CHART_COLORS.amount} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function StatsDaysView({ days }: { days: OrgStatsDay[] }) {
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

  return (
    <>
      <div className="stats-days-head">
        <h2>{t('stats.calendar')}</h2>
        <div className="preset-bar">
          <button
            type="button"
            className={view === 'table' ? 'active' : ''}
            onClick={() => setView('table')}
          >
            {t('stats.viewTable')}
          </button>
          <button
            type="button"
            className={view === 'chart' ? 'active' : ''}
            onClick={() => setView('chart')}
          >
            {t('stats.viewChart')}
          </button>
        </div>
      </div>
      {days.length === 0 ? (
        <p className="muted">{t('common.empty')}</p>
      ) : view === 'table' ? (
        <table>
          <thead>
            <tr>
              <th>{t('stats.day')}</th>
              <th>{t('task.type.transcribe')}</th>
              <th>{t('task.type.summarize')}</th>
              <th>{t('stats.transcribedAudio')}</th>
              <th>{t('stats.summaryChars')}</th>
              <th>{t('stats.spent')}</th>
            </tr>
          </thead>
          <tbody>
            {days.map((day) => (
              <tr key={day.date}>
                <td>{day.date}</td>
                <td>{day.tasks_transcribe_success}</td>
                <td>{day.tasks_summarize_success}</td>
                <td>{formatAudioTime(day.audio_transcribed_sec, t)}</td>
                <td>{day.summary_chars}</td>
                <td>{day.amount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <StatsDaysCharts days={chartDays} />
      )}
    </>
  )
}
