import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import type { OrgStats } from '../types'
import { ErrorBox, formatAudioTime } from '../util'

export function StatsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [stats, setStats] = useState<OrgStats | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const hasOrg = Boolean(me?.org)

  useEffect(() => {
    if (!hasOrg) return
    api<OrgStats>('/org/stats')
      .then(setStats)
      .catch(setErr)
  }, [hasOrg])

  if (!hasOrg) return <Navigate to="/app/profile" replace />

  return (
    <div>
      <h1>{t('stats.title')}</h1>
      <ErrorBox err={err} />
      {stats && (
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
        </div>
      )}
    </div>
  )
}
