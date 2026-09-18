import { useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { LIBRARY_DEFAULT } from '../routes'
import type { OrgStats, User } from '../types'
import { StatsDaysView } from '../components/StatsDaysView'
import { StatsFiltersPanel } from '../components/StatsFiltersPanel'
import { AdminPage } from '../components/AdminSection'
import { StatsSummaryGrid } from '../components/StatsSummaryGrid'
import { showError } from '../util'

export function StatsPage() {
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
    <AdminPage>
      <StatsFiltersPanel
        fromDay={fromDay}
        toDay={toDay}
        onFromChange={setFromDay}
        onToChange={setToDay}
        userId={userId}
        onUserIdChange={setUserId}
        users={users}
        kind={kind}
        onKindChange={setKind}
      />
      {stats && (
        <>
          <StatsSummaryGrid
            tasksTranscribe={stats.tasks_transcribe_success}
            tasksSummarize={stats.tasks_summarize_success}
            audioSec={stats.audio_transcribed_sec}
            summaryChars={stats.summary_chars}
            amount={stats.total_amount}
            amountLabelKey="stats.statSpent"
            amountTooltipKey="stats.spent"
            fromDay={fromDay}
            toDay={toDay}
          />
          <StatsDaysView days={stats.days} />
        </>
      )}
    </AdminPage>
  )
}
