import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import type { InstanceSnapshot, InstanceStats, Org } from '../../types'
import { datePreset, statsRangeForDays } from '../../util/date'
import { formatAudioTime, showError } from '../../util'

export function InstanceStatsTab() {
  const { t } = useTranslation()
  const [snapshot, setSnapshot] = useState<InstanceSnapshot | null>(null)
  const [stats, setStats] = useState<InstanceStats | null>(null)
  const [statsOrgs, setStatsOrgs] = useState<Org[]>([])
  const [fromDay, setFromDay] = useState(() => statsRangeForDays(7).from)
  const [toDay, setToDay] = useState(() => statsRangeForDays(7).to)
  const [statsOrgId, setStatsOrgId] = useState('')
  const [statsUserId, setStatsUserId] = useState('')
  const [statsKind, setStatsKind] = useState('')

  const statsQuery = useMemo(() => {
    const params = new URLSearchParams()
    if (fromDay) params.set('from', fromDay)
    if (toDay) params.set('to', toDay)
    if (statsOrgId) params.set('org_id', statsOrgId)
    if (statsUserId) params.set('user_id', statsUserId)
    if (statsKind) params.set('kind', statsKind)
    const text = params.toString()
    return text ? `?${text}` : ''
  }, [fromDay, toDay, statsOrgId, statsUserId, statsKind])

  const statsUsers = useMemo(() => {
    if (!statsOrgId) return []
    return statsOrgs.find((o) => o.id === statsOrgId)?.members || []
  }, [statsOrgs, statsOrgId])

  useEffect(() => {
    api<{ items: Org[] }>('/orgs?include_hidden=true').then((r) => setStatsOrgs(r.items)).catch(showError)
  }, [])

  useEffect(() => {
    api<InstanceStats>('/instance/stats')
      .then((r) => setSnapshot({
        orgs: r.orgs,
        users: r.users,
        tasks_queued: r.tasks_queued,
        tasks_running: r.tasks_running,
      }))
      .catch(showError)
  }, [])

  useEffect(() => {
    api<InstanceStats>(`/instance/stats${statsQuery}`)
      .then(setStats)
      .catch(showError)
  }, [statsQuery])

  return (
    <>
      {snapshot && (
        <div className="stat-grid">
          <div className="stat">
            <div className="stat-label">{t('instance.orgs')}</div>
            <div className="stat-value">{snapshot.orgs}</div>
          </div>
          <div className="stat">
            <div className="stat-label">{t('instance.users')}</div>
            <div className="stat-value">{snapshot.users}</div>
          </div>
          <div className="stat">
            <div className="stat-label">{t('instance.queued')}</div>
            <div className="stat-value">{snapshot.tasks_queued}</div>
          </div>
          <div className="stat">
            <div className="stat-label">{t('instance.running')}</div>
            <div className="stat-value">{snapshot.tasks_running}</div>
          </div>
        </div>
      )}

      <div className="card stack stats-filters">
        <div className="row wrap">
          <label>{t('stats.from')}<input type="date" value={fromDay} onChange={(e) => setFromDay(e.target.value)} /></label>
          <label>{t('stats.to')}<input type="date" value={toDay} onChange={(e) => setToDay(e.target.value)} /></label>
          <label>
            {t('instance.orgs')}
            <select
              value={statsOrgId}
              onChange={(e) => {
                setStatsOrgId(e.target.value)
                setStatsUserId('')
              }}
            >
              <option value="">{t('common.all')}</option>
              {statsOrgs.map((o) => (
                <option key={o.id} value={o.id}>{o.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t('stats.user')}
            <select
              value={statsUserId}
              disabled={!statsOrgId}
              onChange={(e) => setStatsUserId(e.target.value)}
            >
              <option value="">{t('common.all')}</option>
              {statsUsers.map((u) => (
                <option key={u.id} value={u.id}>{u.email}</option>
              ))}
            </select>
          </label>
          <label>
            {t('stats.kind')}
            <select value={statsKind} onChange={(e) => setStatsKind(e.target.value)}>
              <option value="">{t('common.all')}</option>
              <option value="transcribe">{t('task.type.transcribe')}</option>
              <option value="summarize">{t('task.type.summarize')}</option>
            </select>
          </label>
        </div>
        <div className="row wrap">
          <button type="button" onClick={() => datePreset(7, setFromDay, setToDay)}>{t('stats.days7')}</button>
          <button type="button" onClick={() => datePreset(30, setFromDay, setToDay)}>{t('stats.days30')}</button>
          <button type="button" onClick={() => datePreset('month', setFromDay, setToDay)}>{t('stats.month')}</button>
          <button type="button" onClick={() => datePreset('all', setFromDay, setToDay)}>{t('stats.allTime')}</button>
        </div>
      </div>
      {stats && (
        <>
          <div className="stat-grid">
            <div className="stat">
              <div className="stat-label">{t('instance.transcribeDone')}</div>
              <div className="stat-value">{stats.tasks_transcribe_success}</div>
            </div>
            <div className="stat">
              <div className="stat-label">{t('instance.summarizeDone')}</div>
              <div className="stat-value">{stats.tasks_summarize_success}</div>
            </div>
            <div className="stat">
              <div className="stat-label">{t('instance.transcribedAudio')}</div>
              <div className="stat-value">{formatAudioTime(stats.audio_transcribed_sec, t)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">{t('stats.summaryChars')}</div>
              <div className="stat-value">{stats.summary_chars}</div>
            </div>
            <div className="stat">
              <div className="stat-label">{t('instance.usage')}</div>
              <div className="stat-value">{stats.usage_total}</div>
            </div>
          </div>
          <h2>{t('stats.calendar')}</h2>
          {stats.days.length === 0 ? (
            <p className="muted">{t('common.empty')}</p>
          ) : (
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
                {stats.days.map((day) => (
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
          )}
        </>
      )}
    </>
  )
}
