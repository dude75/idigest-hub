import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isInstanceAdmin, useAuth } from '../auth'
import { LIBRARY_DEFAULT } from '../routes'
import { detectLedgerPreset, OrgLedgerModal } from '../components/OrgLedgerModal'
import type { InstanceSettings, InstanceSnapshot, InstanceStats, Org, OrgLedger, Skill, Tariff, Worker } from '../types'
import { formatAudioTime, fmtDate, showError } from '../util'

const MAX_UPLOAD = 1073741824
type Tab = 'workers' | 'tariffs' | 'orgs' | 'settings' | 'baseSkills' | 'stats'
const TABS: Tab[] = ['stats', 'workers', 'tariffs', 'orgs', 'settings', 'baseSkills']

function utcDay(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function statsRangeForDays(days: number): { from: string; to: string } {
  const to = new Date()
  const from = new Date(to.getTime() - (days - 1) * 86400000)
  return { from: utcDay(from), to: utcDay(to) }
}

function healthLabel(w: Worker): string {
  const health = w.last_health
  if (!health) return '—'
  const http = health._http
  const ready = health._ready_http
  const parts = [
    w.last_seen_version || '',
    http != null ? `http ${String(http)}` : '',
    ready != null ? `ready ${String(ready)}` : '',
  ]
  const text = parts.filter(Boolean).join(' · ')
  return text || JSON.stringify(health)
}

const emptyWorker = {
  type: 'transcribe',
  name: '',
  base_url: '',
  api_token: '',
  weight: 1,
  enabled: true,
}

const emptyTariff = {
  name: '',
  unlimited: false,
  available_on_signup: false,
  price_per_audio_sec: '0',
  price_per_summarize_job: '0',
  price_per_1k_summary_chars: '0',
  audio_retention_days: 0,
  api_enabled: true,
  signup_credit: '0',
  max_upload_bytes: MAX_UPLOAD,
}

export function InstancePage() {
  const { t } = useTranslation()
  const { me, refresh } = useAuth()
  const [search, setSearch] = useSearchParams()
  const tabParam = search.get('tab')
  const tab: Tab = TABS.includes(tabParam as Tab) ? (tabParam as Tab) : 'stats'
  function setTab(id: Tab) {
    setSearch(id === 'stats' ? {} : { tab: id }, { replace: true })
  }
  const [workers, setWorkers] = useState<Worker[]>([])
  const [wform, setWform] = useState(emptyWorker)
  const [editW, setEditW] = useState<string | null>(null)
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [tform, setTform] = useState(emptyTariff)
  const [editT, setEditT] = useState<string | null>(null)
  const [orgs, setOrgs] = useState<Org[]>([])
  const [settings, setSettings] = useState<InstanceSettings | null>(null)
  const [smtpPassword, setSmtpPassword] = useState('')
  const [skills, setSkills] = useState<Skill[]>([])
  const [sname, setSname] = useState('')
  const [sbody, setSbody] = useState('')
  const [snapshot, setSnapshot] = useState<InstanceSnapshot | null>(null)
  const [stats, setStats] = useState<InstanceStats | null>(null)
  const [statsOrgs, setStatsOrgs] = useState<Org[]>([])
  const [fromDay, setFromDay] = useState(() => statsRangeForDays(7).from)
  const [toDay, setToDay] = useState(() => statsRangeForDays(7).to)
  const [statsOrgId, setStatsOrgId] = useState('')
  const [statsUserId, setStatsUserId] = useState('')
  const [statsKind, setStatsKind] = useState('')
  const [deltas, setDeltas] = useState<Record<string, string>>({})
  const [showHiddenOrgs, setShowHiddenOrgs] = useState(false)
  const [hiddenOrgCount, setHiddenOrgCount] = useState(0)
  const [orgCard, setOrgCard] = useState<Org | null>(null)
  const [orgLedger, setOrgLedger] = useState<OrgLedger | null>(null)
  const [orgFromDay, setOrgFromDay] = useState(() => statsRangeForDays(7).from)
  const [orgToDay, setOrgToDay] = useState(() => statsRangeForDays(7).to)
  const [orgUserId, setOrgUserId] = useState('')
  const [orgKind, setOrgKind] = useState('')

  const allowed = isInstanceAdmin(me)

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

  const orgLedgerQuery = useMemo(() => {
    const params = new URLSearchParams()
    if (orgFromDay) params.set('from', orgFromDay)
    if (orgToDay) params.set('to', orgToDay)
    if (orgUserId) params.set('user_id', orgUserId)
    if (orgKind) params.set('kind', orgKind)
    const text = params.toString()
    return text ? `?${text}` : ''
  }, [orgFromDay, orgToDay, orgUserId, orgKind])

  const orgActivePreset = useMemo(
    () => detectLedgerPreset(orgFromDay, orgToDay, utcDay),
    [orgFromDay, orgToDay],
  )

  async function load() {
    try {
      if (tab === 'workers') {
        setWorkers((await api<{ items: Worker[] }>('/workers')).items)
      } else if (tab === 'tariffs') {
        setTariffs((await api<{ items: Tariff[] }>('/tariffs')).items)
      } else if (tab === 'orgs') {
        const orgQuery = showHiddenOrgs ? '?include_hidden=true' : ''
        const [o, tr] = await Promise.all([
          api<{ items: Org[]; hidden_count: number }>(`/orgs${orgQuery}`),
          api<{ items: Tariff[] }>('/tariffs'),
        ])
        setOrgs(o.items)
        setHiddenOrgCount(o.hidden_count ?? 0)
        setTariffs(tr.items)
      } else if (tab === 'settings') {
        setSettings(await api<InstanceSettings>('/instance/settings'))
      } else if (tab === 'baseSkills') {
        setSkills((await api<{ items: Skill[] }>('/skills/base')).items)
      }
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    if (!allowed) return
    if (tab === 'stats') return
    void load()
  }, [tab, allowed, showHiddenOrgs])

  useEffect(() => {
    if (!allowed || tab !== 'stats') return
    api<{ items: Org[] }>('/orgs?include_hidden=true').then((r) => setStatsOrgs(r.items)).catch(showError)
  }, [allowed, tab])

  useEffect(() => {
    if (!allowed || tab !== 'stats') return
    api<InstanceStats>('/instance/stats')
      .then((r) => setSnapshot({
        orgs: r.orgs,
        users: r.users,
        tasks_queued: r.tasks_queued,
        tasks_running: r.tasks_running,
      }))
      .catch(showError)
  }, [allowed, tab])

  useEffect(() => {
    if (!allowed || tab !== 'stats') return
    api<InstanceStats>(`/instance/stats${statsQuery}`)
      .then(setStats)
      .catch(showError)
  }, [allowed, tab, statsQuery])

  useEffect(() => {
    if (!allowed || !orgCard) return
    api<OrgLedger>(`/orgs/${orgCard.id}/ledger${orgLedgerQuery}`)
      .then(setOrgLedger)
      .catch(showError)
  }, [allowed, orgCard, orgLedgerQuery])

  function openOrgCard(org: Org) {
    const range = statsRangeForDays(7)
    setOrgFromDay(range.from)
    setOrgToDay(range.to)
    setOrgUserId('')
    setOrgKind('')
    setOrgLedger(null)
    setOrgCard(org)
  }

  function statsPreset(days: number | 'month' | 'all') {
    if (days === 'all') {
      setFromDay('')
      setToDay('')
      return
    }
    const to = new Date()
    if (days === 'month') {
      const start = new Date(Date.UTC(to.getUTCFullYear(), to.getUTCMonth(), 1))
      setFromDay(utcDay(start))
      setToDay(utcDay(to))
      return
    }
    const range = statsRangeForDays(days)
    setFromDay(range.from)
    setToDay(range.to)
  }

  function orgPreset(days: number | 'month' | 'all') {
    if (days === 'all') {
      setOrgFromDay('')
      setOrgToDay('')
      return
    }
    const to = new Date()
    if (days === 'month') {
      const start = new Date(Date.UTC(to.getUTCFullYear(), to.getUTCMonth(), 1))
      setOrgFromDay(utcDay(start))
      setOrgToDay(utcDay(to))
      return
    }
    const range = statsRangeForDays(days)
    setOrgFromDay(range.from)
    setOrgToDay(range.to)
  }

  if (!allowed) return <Navigate to={LIBRARY_DEFAULT} replace />

  async function saveWorker() {
    const body = { ...wform, weight: Number(wform.weight) }
    if (editW) {
      await api(`/workers/${editW}`, { method: 'PATCH', body: JSON.stringify(body) })
    } else {
      await api('/workers', { method: 'POST', body: JSON.stringify(body) })
    }
    setWform(emptyWorker)
    setEditW(null)
    await load()
  }

  async function saveTariff() {
    const body = { ...tform, max_upload_bytes: Math.min(Number(tform.max_upload_bytes) || MAX_UPLOAD, MAX_UPLOAD) }
    if (editT) {
      await api(`/tariffs/${editT}`, { method: 'PATCH', body: JSON.stringify(body) })
    } else {
      await api('/tariffs', { method: 'POST', body: JSON.stringify(body) })
    }
    setTform(emptyTariff)
    setEditT(null)
    await load()
  }

  async function toggleOrgHidden(org: Org) {
    try {
      await api(`/orgs/${org.id}/${org.hidden ? 'unhide' : 'hide'}`, { method: 'POST' })
      await load()
    } catch (e) {
      showError(e)
    }
  }

  async function saveSettings() {
    if (!settings) return
    await api('/instance/settings', {
      method: 'PATCH',
      body: JSON.stringify({
        allow_new_orgs: settings.allow_new_orgs,
        public_base_url: settings.public_base_url,
        smtp_host: settings.smtp_host,
        smtp_port: settings.smtp_port,
        smtp_user: settings.smtp_user,
        smtp_from: settings.smtp_from,
        smtp_tls: settings.smtp_tls,
        asr_model: settings.asr_model,
        diarization_model: settings.diarization_model || '',
        rate_limit_enabled: settings.rate_limit_enabled,
        rate_limit_login_email: settings.rate_limit_login_email,
        rate_limit_login_ip: settings.rate_limit_login_ip,
        rate_limit_login_global: settings.rate_limit_login_global,
        rate_limit_signup_email: settings.rate_limit_signup_email,
        rate_limit_signup_ip: settings.rate_limit_signup_ip,
        rate_limit_signup_global: settings.rate_limit_signup_global,
        rate_limit_reset_email: settings.rate_limit_reset_email,
        rate_limit_reset_ip: settings.rate_limit_reset_ip,
        rate_limit_reset_global: settings.rate_limit_reset_global,
        rate_limit_reset_confirm_ip: settings.rate_limit_reset_confirm_ip,
        rate_limit_reset_confirm_global: settings.rate_limit_reset_confirm_global,
        rate_limit_setup_ip: settings.rate_limit_setup_ip,
        rate_limit_setup_global: settings.rate_limit_setup_global,
        rate_limit_api_user: settings.rate_limit_api_user,
        rate_limit_api_ip: settings.rate_limit_api_ip,
        rate_limit_api_global: settings.rate_limit_api_global,
        rate_limit_api_tasks_user: settings.rate_limit_api_tasks_user,
        rate_limit_api_tasks_ip: settings.rate_limit_api_tasks_ip,
        ...(smtpPassword ? { smtp_password: smtpPassword } : {}),
      }),
    })
    setSmtpPassword('')
    await load()
  }

  return (
    <div>
      <h1>{t('instance.title')}</h1>
      <div className="tabs">
        {TABS.map((id) => (
          <button key={id} type="button" className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
            {t(`instance.${id}`)}
          </button>
        ))}
      </div>

      {tab === 'stats' && snapshot && (
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

      {tab === 'stats' && (
        <>
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
              <button type="button" onClick={() => statsPreset(7)}>{t('stats.days7')}</button>
              <button type="button" onClick={() => statsPreset(30)}>{t('stats.days30')}</button>
              <button type="button" onClick={() => statsPreset('month')}>{t('stats.month')}</button>
              <button type="button" onClick={() => statsPreset('all')}>{t('stats.allTime')}</button>
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
      )}

      {tab === 'workers' && (
        <>
          <div className="card stack">
            <label>{t('instance.type')}
              <select value={wform.type} onChange={(e) => setWform({ ...wform, type: e.target.value })}>
                <option value="transcribe">{t('instance.transcribe')}</option>
                <option value="summarize">{t('instance.summarize')}</option>
              </select>
            </label>
            <label>{t('common.name')}<input value={wform.name} onChange={(e) => setWform({ ...wform, name: e.target.value })} /></label>
            <label>{t('instance.baseUrl')}<input value={wform.base_url} onChange={(e) => setWform({ ...wform, base_url: e.target.value })} /></label>
            <label>{t('instance.apiToken')}<input value={wform.api_token} onChange={(e) => setWform({ ...wform, api_token: e.target.value })} /></label>
            <label>{t('instance.weight')}<input type="number" min={1} value={wform.weight} onChange={(e) => setWform({ ...wform, weight: Number(e.target.value) })} /></label>
            <label className="row">
              <input type="checkbox" checked={wform.enabled} onChange={(e) => setWform({ ...wform, enabled: e.target.checked })} />
              {t('instance.enabled')}
            </label>
            <button className="primary" type="button" onClick={() => void saveWorker()}>{editW ? t('common.save') : t('common.create')}</button>
          </div>
          <table>
            <thead>
              <tr>
                <th>{t('common.name')}</th>
                <th>{t('instance.type')}</th>
                <th>{t('instance.health')}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {workers.map((w) => (
                <tr key={w.id}>
                  <td>{w.name || w.base_url}</td>
                  <td>{w.type} · w{w.weight} {w.enabled ? '' : `(${t('common.disable')})`}</td>
                  <td>{healthLabel(w)}</td>
                  <td className="row">
                    <button type="button" onClick={() => { setEditW(w.id); setWform({ type: w.type, name: w.name, base_url: w.base_url, api_token: '', weight: w.weight, enabled: w.enabled }) }}>{t('common.edit')}</button>
                    <button type="button" className="danger" onClick={() => void api(`/workers/${w.id}`, { method: 'DELETE' }).then(load)}>{t('common.delete')}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'tariffs' && (
        <>
          <div className="card stack">
            <label>{t('common.name')}<input value={tform.name} onChange={(e) => setTform({ ...tform, name: e.target.value })} /></label>
            <label className="row">
              <input type="checkbox" checked={tform.unlimited} onChange={(e) => setTform({ ...tform, unlimited: e.target.checked })} />
              {t('instance.unlimited')}
            </label>
            <label className="row">
              <input type="checkbox" checked={tform.available_on_signup} onChange={(e) => setTform({ ...tform, available_on_signup: e.target.checked })} />
              {t('instance.signup')}
            </label>
            <label>{t('instance.priceAudio')}<input value={tform.price_per_audio_sec} onChange={(e) => setTform({ ...tform, price_per_audio_sec: e.target.value })} /></label>
            <label>{t('instance.priceJob')}<input value={tform.price_per_summarize_job} onChange={(e) => setTform({ ...tform, price_per_summarize_job: e.target.value })} /></label>
            <label>{t('instance.priceText')}<input value={tform.price_per_1k_summary_chars} onChange={(e) => setTform({ ...tform, price_per_1k_summary_chars: e.target.value })} /></label>
            <label>{t('instance.retentionDays')}<input type="number" min={0} value={tform.audio_retention_days} onChange={(e) => setTform({ ...tform, audio_retention_days: Number(e.target.value) })} /></label>
            <label className="row">
              <input type="checkbox" checked={tform.api_enabled} onChange={(e) => setTform({ ...tform, api_enabled: e.target.checked })} />
              {t('instance.apiEnabled')}
            </label>
            <label>{t('instance.signupCredit')}<input value={tform.signup_credit} onChange={(e) => setTform({ ...tform, signup_credit: e.target.value })} /></label>
            <label>{t('instance.uploadCap')}<input type="number" max={MAX_UPLOAD} value={tform.max_upload_bytes} onChange={(e) => setTform({ ...tform, max_upload_bytes: Number(e.target.value) })} /></label>
            <button className="primary" type="button" onClick={() => void saveTariff()}>{editT ? t('common.save') : t('common.create')}</button>
          </div>
          <table>
            <thead>
              <tr>
                <th>{t('common.name')}</th>
                <th>{t('instance.orgCount')}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {tariffs.map((tr) => (
                <tr key={tr.id}>
                  <td>
                    {tr.name} {tr.unlimited && <span className="badge">{t('instance.unlimited')}</span>}
                    {tr.available_on_signup && <span className="badge out">{t('instance.signup')}</span>}
                    {tr.archived && <span className="badge warn">{t('instance.archived')}</span>}
                    <div className="muted">{tr.price_per_audio_sec} / {tr.price_per_summarize_job} / {tr.price_per_1k_summary_chars} · {tr.max_upload_bytes}</div>
                  </td>
                  <td>{tr.org_count ?? 0}</td>
                  <td className="row">
                    <button type="button" onClick={() => {
                      setEditT(tr.id)
                      setTform({
                        name: tr.name,
                        unlimited: tr.unlimited,
                        available_on_signup: tr.available_on_signup,
                        price_per_audio_sec: tr.price_per_audio_sec,
                        price_per_summarize_job: tr.price_per_summarize_job,
                        price_per_1k_summary_chars: tr.price_per_1k_summary_chars,
                        audio_retention_days: tr.audio_retention_days,
                        api_enabled: tr.api_enabled,
                        signup_credit: tr.signup_credit,
                        max_upload_bytes: tr.max_upload_bytes,
                      })
                    }}>{t('common.edit')}</button>
                    {tr.archived ? (
                      <button type="button" onClick={() => void api(`/tariffs/${tr.id}/unarchive`, { method: 'POST' }).then(load)}>{t('instance.unarchive')}</button>
                    ) : (
                      <button type="button" onClick={() => void api(`/tariffs/${tr.id}/archive`, { method: 'POST' }).then(load)}>{t('instance.archive')}</button>
                    )}
                    <button type="button" className="danger" onClick={() => void api(`/tariffs/${tr.id}`, { method: 'DELETE' }).then(load).catch(showError)}>{t('common.delete')}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'orgs' && (
        <>
          <label className="row" style={{ marginBottom: 12 }}>
            <input type="checkbox" checked={showHiddenOrgs} onChange={(e) => setShowHiddenOrgs(e.target.checked)} />
            {t('library.showHidden', { count: hiddenOrgCount })}
          </label>
          <div className="org-cards">
          {orgs.length === 0 && <p className="muted">{t('common.empty')}</p>}
          {orgs.map((o) => (
            <article className="org-card" key={o.id}>
              <section className="org-tile org-tile-info">
                <h3 className="org-card-title">{o.name}</h3>
                <div className="org-card-meta">
                  <span className="badge">{o.tariff.name}</span>
                  {o.unlimited ? (
                    <span className="badge out">{t('wallet.unlimited')}</span>
                  ) : (
                    <span className="org-balance">{o.balance}</span>
                  )}
                  {o.hidden && <span className="badge">{t('library.hidden')}</span>}
                  <span className="muted org-member-count">
                    {t('instance.users')} · {(o.members || []).length}
                  </span>
                </div>
                <div className="org-card-foot">
                  <button type="button" className="org-ledger-btn" onClick={() => openOrgCard(o)}>
                    {t('instance.ledger')} →
                  </button>
                  <button
                    type="button"
                    className="org-hide-btn"
                    title={t('instance.orgHideHint')}
                    onClick={() => void toggleOrgHidden(o)}
                  >
                    {o.hidden ? t('common.unhide') : t('common.hide')}
                  </button>
                </div>
              </section>
              <section className="org-tile org-tile-ops">
                <div className="org-ops-toolbar">
                  <label className="org-ops-field">
                    <span>{t('org.tariff')}</span>
                    <select
                      value={o.tariff.id}
                      onChange={(e) => void api(`/orgs/${o.id}/tariff`, { method: 'PATCH', body: JSON.stringify({ tariff_id: e.target.value }) }).then(load)}
                    >
                      {tariffs.map((tr) => (
                        <option key={tr.id} value={tr.id}>{tr.name}</option>
                      ))}
                    </select>
                  </label>
                  <div className="org-ops-field org-wallet-field">
                    <span>{t('instance.walletDelta')}</span>
                    <div className="org-wallet-inline">
                      <input
                        placeholder="+100"
                        value={deltas[o.id] || ''}
                        onChange={(e) => setDeltas((d) => ({ ...d, [o.id]: e.target.value }))}
                      />
                      <button
                        type="button"
                        className="primary"
                        onClick={() => void api(`/orgs/${o.id}/wallet`, { method: 'POST', body: JSON.stringify({ delta: deltas[o.id] }) }).then(load)}
                      >
                        {t('instance.apply')}
                      </button>
                    </div>
                  </div>
                </div>
                {(o.members || []).length > 0 && (
                  <details className="org-users">
                    <summary>{t('instance.users')}</summary>
                    <ul className="org-users-list">
                      {(o.members || []).map((u) => (
                        <li className="org-user" key={u.id}>
                          <span className="org-user-email" title={u.email}>{u.email}</span>
                          <span className="badge">{u.role}</span>
                          {!u.is_instance_admin && (
                            <button
                              type="button"
                              onClick={() => void api('/impersonate', { method: 'POST', body: JSON.stringify({ user_id: u.id }) }).then(() => refresh())}
                            >
                              {t('instance.impersonate')}
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </section>
            </article>
          ))}
          </div>
        </>
      )}

      {tab === 'settings' && settings && (
        <div className="card stack">
          <label className="row">
            <input type="checkbox" checked={settings.allow_new_orgs} onChange={(e) => setSettings({ ...settings, allow_new_orgs: e.target.checked })} />
            {t('instance.allowNewOrgs')}
          </label>
          <label>{t('instance.publicBaseUrl')}<input value={settings.public_base_url || ''} onChange={(e) => setSettings({ ...settings, public_base_url: e.target.value })} /></label>
          <label>{t('instance.asr')}<input value={settings.asr_model} onChange={(e) => setSettings({ ...settings, asr_model: e.target.value })} /></label>
          <label>{t('instance.diarization')}<input value={settings.diarization_model || ''} onChange={(e) => setSettings({ ...settings, diarization_model: e.target.value || null })} /></label>
          <label>{t('instance.smtpHost')}<input value={settings.smtp_host || ''} onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value })} /></label>
          <label>{t('instance.smtpPort')}<input type="number" value={settings.smtp_port ?? ''} onChange={(e) => setSettings({ ...settings, smtp_port: e.target.value ? Number(e.target.value) : null })} /></label>
          <label>{t('instance.smtpUser')}<input value={settings.smtp_user || ''} onChange={(e) => setSettings({ ...settings, smtp_user: e.target.value })} /></label>
          <label>{t('instance.smtpPassword')}<input type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} /></label>
          <label>{t('instance.smtpFrom')}<input value={settings.smtp_from || ''} onChange={(e) => setSettings({ ...settings, smtp_from: e.target.value })} /></label>
          <label className="row">
            <input type="checkbox" checked={settings.smtp_tls} onChange={(e) => setSettings({ ...settings, smtp_tls: e.target.checked })} />
            {t('instance.smtpTls')}
          </label>

          <details className="fold">
            <summary>{t('instance.rateLimitTitle')}</summary>
            <div className="stack">
              <p className="muted">{t('instance.rateLimitHint')}</p>
              <label className="row">
                <input type="checkbox" checked={settings.rate_limit_enabled} onChange={(e) => setSettings({ ...settings, rate_limit_enabled: e.target.checked })} />
                {t('instance.rateLimitEnabled')}
              </label>
              <fieldset className="stack" disabled={!settings.rate_limit_enabled}>
                <legend>{t('instance.rateLimitLogin')}</legend>
                <label>{t('instance.rateLimitPerEmailMin')}<input type="number" min={0} value={settings.rate_limit_login_email} onChange={(e) => setSettings({ ...settings, rate_limit_login_email: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitPerIpMin')}<input type="number" min={0} value={settings.rate_limit_login_ip} onChange={(e) => setSettings({ ...settings, rate_limit_login_ip: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitGlobalMin')}<input type="number" min={0} value={settings.rate_limit_login_global} onChange={(e) => setSettings({ ...settings, rate_limit_login_global: Number(e.target.value) })} /></label>
              </fieldset>
              <fieldset className="stack" disabled={!settings.rate_limit_enabled}>
                <legend>{t('instance.rateLimitSignup')}</legend>
                <label>{t('instance.rateLimitPerEmailMin')}<input type="number" min={0} value={settings.rate_limit_signup_email} onChange={(e) => setSettings({ ...settings, rate_limit_signup_email: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitPerIpMin')}<input type="number" min={0} value={settings.rate_limit_signup_ip} onChange={(e) => setSettings({ ...settings, rate_limit_signup_ip: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitGlobalMin')}<input type="number" min={0} value={settings.rate_limit_signup_global} onChange={(e) => setSettings({ ...settings, rate_limit_signup_global: Number(e.target.value) })} /></label>
              </fieldset>
              <fieldset className="stack" disabled={!settings.rate_limit_enabled}>
                <legend>{t('instance.rateLimitReset')}</legend>
                <label>{t('instance.rateLimitPerEmailHour')}<input type="number" min={0} value={settings.rate_limit_reset_email} onChange={(e) => setSettings({ ...settings, rate_limit_reset_email: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitPerIpHour')}<input type="number" min={0} value={settings.rate_limit_reset_ip} onChange={(e) => setSettings({ ...settings, rate_limit_reset_ip: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitGlobalHour')}<input type="number" min={0} value={settings.rate_limit_reset_global} onChange={(e) => setSettings({ ...settings, rate_limit_reset_global: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitConfirmPerIpHour')}<input type="number" min={0} value={settings.rate_limit_reset_confirm_ip} onChange={(e) => setSettings({ ...settings, rate_limit_reset_confirm_ip: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitConfirmGlobalHour')}<input type="number" min={0} value={settings.rate_limit_reset_confirm_global} onChange={(e) => setSettings({ ...settings, rate_limit_reset_confirm_global: Number(e.target.value) })} /></label>
              </fieldset>
              <fieldset className="stack" disabled={!settings.rate_limit_enabled}>
                <legend>{t('instance.rateLimitSetup')}</legend>
                <label>{t('instance.rateLimitPerIpHour')}<input type="number" min={0} value={settings.rate_limit_setup_ip} onChange={(e) => setSettings({ ...settings, rate_limit_setup_ip: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitGlobalHour')}<input type="number" min={0} value={settings.rate_limit_setup_global} onChange={(e) => setSettings({ ...settings, rate_limit_setup_global: Number(e.target.value) })} /></label>
              </fieldset>
              <fieldset className="stack" disabled={!settings.rate_limit_enabled}>
                <legend>{t('instance.rateLimitApi')}</legend>
                <label>{t('instance.rateLimitPerUserMin')}<input type="number" min={0} value={settings.rate_limit_api_user} onChange={(e) => setSettings({ ...settings, rate_limit_api_user: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitPerIpMin')}<input type="number" min={0} value={settings.rate_limit_api_ip} onChange={(e) => setSettings({ ...settings, rate_limit_api_ip: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitGlobalMin')}<input type="number" min={0} value={settings.rate_limit_api_global} onChange={(e) => setSettings({ ...settings, rate_limit_api_global: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitTasksPerUserMin')}<input type="number" min={0} value={settings.rate_limit_api_tasks_user} onChange={(e) => setSettings({ ...settings, rate_limit_api_tasks_user: Number(e.target.value) })} /></label>
                <label>{t('instance.rateLimitTasksPerIpMin')}<input type="number" min={0} value={settings.rate_limit_api_tasks_ip} onChange={(e) => setSettings({ ...settings, rate_limit_api_tasks_ip: Number(e.target.value) })} /></label>
              </fieldset>
            </div>
          </details>

          <button className="primary" type="button" onClick={() => void saveSettings()}>{t('common.save')}</button>
        </div>
      )}

      {orgCard && (
        <OrgLedgerModal
          org={orgCard}
          ledger={orgLedger}
          fromDay={orgFromDay}
          toDay={orgToDay}
          userId={orgUserId}
          kind={orgKind}
          activePreset={orgActivePreset}
          onClose={() => setOrgCard(null)}
          onFromDayChange={setOrgFromDay}
          onToDayChange={setOrgToDay}
          onUserIdChange={setOrgUserId}
          onKindChange={setOrgKind}
          onPreset={orgPreset}
        />
      )}

      {tab === 'baseSkills' && (
        <>
          <div className="card stack">
            <label>{t('common.name')}<input value={sname} onChange={(e) => setSname(e.target.value)} /></label>
            <label>{t('skills.body')}<textarea className="skill-editor" value={sbody} onChange={(e) => setSbody(e.target.value)} /></label>
            <button className="primary" type="button" onClick={() => void api('/skills/base', { method: 'POST', body: JSON.stringify({ name: sname, body: sbody }) }).then(() => { setSname(''); setSbody(''); return load() })}>
              {t('common.create')}
            </button>
          </div>
          <div className="list">
            {skills.length === 0 && <p className="muted">{t('common.empty')}</p>}
            {skills.map((s) => (
              <div className="item row" key={s.id}>
                <div className="grow">
                  <Link className="title" to={`/app/skill/${s.id}`}>{s.name}</Link>
                  <div className="muted">{fmtDate(s.created_at)}</div>
                </div>
                <span className="badge">{s.scope}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
