import { useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { LIBRARY_DEFAULT } from '../routes'
import type { OrgStats, User } from '../types'
import { datePreset } from '../util/date'
import { StatsDaysView } from '../components/StatsDaysView'
import { formatAudioTime, showError } from '../util'

export function StatsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [stats, setStats] = useState<OrgStats | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [fromDay, setFromDay] = useState('')
  const [toDay, setToDay] = useState('')
  const [userId, setUserId] = useState('')
  const [kind, setKind] = useState('')
  const admin = isOrgAdmin(me)
  const hasOrg = Boolean(me?.org)

  const query = useMemo(() => {
    const params = new URLSearchParams()
    if (fromDay) params.set('from', fromDay)
    if (toDay) params.set('to', toDay)
    if (userId) params.set('user_id', userId)
    if (kind) params.set('kind', kind)
    const text = params.toString()
    return text ? `?${text}` : ''
  }, [fromDay, toDay, userId, kind])

  useEffect(() => {
    if (!hasOrg || !admin) return
    api<{ items: User[] }>('/org/users').then((r) => setUsers(r.items)).catch(showError)
  }, [hasOrg, admin])

  useEffect(() => {
    if (!hasOrg || !admin) return
    api<OrgStats>(`/org/stats${query}`)
      .then(setStats)
      .catch(showError)
  }, [hasOrg, admin, query])

  if (!hasOrg) return <Navigate to="/app/profile" replace />
  if (!admin) return <Navigate to={LIBRARY_DEFAULT} replace />

  return (
    <div>
      <h1>{t('stats.title')}</h1>
      <div className="card stack stats-filters">
        <div className="row wrap">
          <label>{t('stats.from')}<input type="date" value={fromDay} onChange={(e) => setFromDay(e.target.value)} /></label>
          <label>{t('stats.to')}<input type="date" value={toDay} onChange={(e) => setToDay(e.target.value)} /></label>
          <label>
            {t('stats.user')}
            <select value={userId} onChange={(e) => setUserId(e.target.value)}>
              <option value="">{t('common.all')}</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.email}</option>
              ))}
            </select>
          </label>
          <label>
            {t('stats.kind')}
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
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
              <div className="stat-label">{t('stats.transcribeDone')}</div>
              <div className="stat-value">{stats.tasks_transcribe_success}</div>
            </div>
            <div className="stat">
              <div className="stat-label">{t('stats.summarizeDone')}</div>
              <div className="stat-value">{stats.tasks_summarize_success}</div>
            </div>
            <div className="stat">
              <div className="stat-label">{t('stats.transcribedAudio')}</div>
              <div className="stat-value">{formatAudioTime(stats.audio_transcribed_sec, t)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">{t('stats.summaryChars')}</div>
              <div className="stat-value">{stats.summary_chars}</div>
            </div>
            <div className="stat">
              <div className="stat-label">{t('stats.spent')}</div>
              <div className="stat-value">{stats.total_amount}</div>
            </div>
          </div>
          <StatsDaysView days={stats.days} />
        </>
      )}
    </div>
  )
}
