import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import type { InstanceSnapshot, InstanceStats, Org } from '../../types'
import { StatsDaysView } from '../../components/StatsDaysView'
import { statsRangeForDays } from '../../util/date'
import { AdminPage } from '../../components/AdminSection'
import { StatCard, StatGrid } from '../../components/StatCard'
import { StatsFiltersPanel } from '../../components/StatsFiltersPanel'
import { StatsSummaryGrid } from '../../components/StatsSummaryGrid'
import { formatInteger, showError } from '../../util'

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
    let cancelled = false
    async function loadSnapshot() {
      try {
        const r = await api<InstanceStats>('/instance/stats')
        if (cancelled) return
        setSnapshot({
          orgs: r.orgs,
          users: r.users,
          tasks_queued: r.tasks_queued,
          tasks_running: r.tasks_running,
          download_proxy_status: r.download_proxy_status,
        })
      } catch (e) {
        if (!cancelled) showError(e)
      }
    }
    void loadSnapshot()
    const timer = window.setInterval(() => void loadSnapshot(), 30_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    api<InstanceStats>(`/instance/stats${statsQuery}`)
      .then(setStats)
      .catch(showError)
  }, [statsQuery])

  return (
    <AdminPage>
      {snapshot && (
        <StatGrid caption={t('instance.snapshotLive')}>
          <StatCard label={t('instance.orgs')} value={formatInteger(snapshot.orgs)} tone="ops" />
          <StatCard label={t('instance.users')} value={formatInteger(snapshot.users)} tone="ops" />
          <StatCard label={t('instance.queued')} value={formatInteger(snapshot.tasks_queued)} tone="ops" />
          <StatCard label={t('instance.running')} value={formatInteger(snapshot.tasks_running)} tone="ops" />
          <StatCard
            label={t('instance.downloadProxyStatus')}
            value={t(`instance.downloadProxyStatusValue.${snapshot.download_proxy_status}`)}
            tone={`proxy-${snapshot.download_proxy_status}` as 'proxy-up' | 'proxy-down' | 'proxy-na'}
          />
        </StatGrid>
      )}

      <StatsFiltersPanel
        fromDay={fromDay}
        toDay={toDay}
        onFromChange={setFromDay}
        onToChange={setToDay}
        orgId={statsOrgId}
        onOrgIdChange={setStatsOrgId}
        orgs={statsOrgs}
        userId={statsUserId}
        onUserIdChange={setStatsUserId}
        users={statsUsers}
        kind={statsKind}
        onKindChange={setStatsKind}
      />
      {stats && (
        <>
          <StatsSummaryGrid
            tasksTranscribe={stats.tasks_transcribe_success}
            tasksSummarize={stats.tasks_summarize_success}
            audioSec={stats.audio_transcribed_sec}
            summaryChars={stats.summary_chars}
            amount={stats.usage_total}
            amountLabelKey="stats.statUsage"
            amountTooltipKey="instance.usage"
            fromDay={fromDay}
            toDay={toDay}
            tooltipPrefix="instance"
          />
          <StatsDaysView
            days={stats.days}
            amountLabelKey="stats.statUsage"
            amountTooltipKey="instance.usage"
          />
        </>
      )}
    </AdminPage>
  )
}
