import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AdminFormCard, AdminPage, AdminTableCard } from '../components/AdminSection'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Modal } from '../components/Modal'
import { StatCard, StatGrid } from '../components/StatCard'
import { TariffDetails } from '../components/TariffDetails'
import { UserStatusBadges } from '../components/UserAgreementBadge'
import { LIBRARY_DEFAULT } from '../routes'
import type { Org, OrgCaptureJitsiHost, OrgCaptureWorkerChoice, OrgSsoAdmin, Tariff, User } from '../types'
import { normalizeJitsiHostInput } from '../util/captureHost'
import { formatDecimal, formatInteger, showError, WalletLabel } from '../util'
import { canAdminResetMemberMfa } from '../mfa'
import { randomPassword } from '../util/password'

function SsoUrlRow({ label, value }: { label: string; value: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="sso-url-row">
      <span className="sso-url-label">{label}</span>
      <code className="sso-url-value" title={value}>{value}</code>
      <button type="button" className="sso-url-copy" onClick={() => void copy()}>
        {copied ? t('profile.copied') : t('common.copy')}
      </button>
    </div>
  )
}

function tariffSelectable(tariffs: Tariff[], current: Tariff): boolean {
  return tariffs.some((tr) => tr.id === current.id)
}

export function OrgPage() {
  const { t } = useTranslation()
  const { me, refresh } = useAuth()
  const nav = useNavigate()
  const [org, setOrg] = useState<Org | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [name, setName] = useState('')
  const [ttl, setTtl] = useState(0)
  const [mfaRequired, setMfaRequired] = useState(false)
  const [allowPublicLinks, setAllowPublicLinks] = useState(true)
  const [tariffId, setTariffId] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'org_admin' | 'org_member'>('org_member')
  const [offUser, setOffUser] = useState<User | null>(null)
  const [action, setAction] = useState<'transfer' | 'wipe'>('wipe')
  const [target, setTarget] = useState('')
  const [tempPw, setTempPw] = useState<{ email: string; password: string } | null>(null)
  const [copiedResetPassword, setCopiedResetPassword] = useState(false)
  const [mfaResetOk, setMfaResetOk] = useState<string | null>(null)
  const [mfaResetUser, setMfaResetUser] = useState<User | null>(null)
  const [mfaResetBusy, setMfaResetBusy] = useState(false)
  const [sso, setSso] = useState<OrgSsoAdmin | null>(null)
  const [ssoIssuer, setSsoIssuer] = useState('')
  const [ssoClientId, setSsoClientId] = useState('')
  const [ssoClientSecret, setSsoClientSecret] = useState('')
  const [ssoEnabled, setSsoEnabled] = useState(false)
  const [copiedAddUserPassword, setCopiedAddUserPassword] = useState(false)
  const [captureAllowed, setCaptureAllowed] = useState(false)
  const [captureBotDisplayName, setCaptureBotDisplayName] = useState('')
  const [captureHosts, setCaptureHosts] = useState<OrgCaptureJitsiHost[]>([])
  const [captureWorkers, setCaptureWorkers] = useState<OrgCaptureWorkerChoice[]>([])
  const [captureEditingId, setCaptureEditingId] = useState<string | null>(null)
  const [captureDraft, setCaptureDraft] = useState({
    host: '',
    jwt_app_id: '',
    jwt_secret: '',
    clear_jwt_secret: false,
  })
  const admin = isOrgAdmin(me)
  const hasOrg = Boolean(me?.org)
  const canConfigureSso = admin && hasOrg

  const summary = useMemo(() => ({
    total: users.length,
    active: users.filter((u) => !u.disabled).length,
    admins: users.filter((u) => u.role === 'org_admin').length,
    disabled: users.filter((u) => u.disabled).length,
  }), [users])

  async function load() {
    const requests: [
      Promise<Org>,
      Promise<{ items: User[] }>,
      Promise<{ items: Tariff[] }>,
      Promise<OrgSsoAdmin> | Promise<null>,
      Promise<{
        allowed: boolean
        bot_display_name?: string
        items: OrgCaptureJitsiHost[]
        workers: OrgCaptureWorkerChoice[]
      }> | Promise<null>,
    ] = [
      api<Org>('/org'),
      api<{ items: User[] }>('/org/users'),
      api<{ items: Tariff[] }>('/org/available-tariffs'),
      admin && hasOrg ? api<OrgSsoAdmin>('/org/sso') : Promise.resolve(null),
      admin && hasOrg
        ? api<{
            allowed: boolean
            bot_display_name?: string
            items: OrgCaptureJitsiHost[]
            workers: OrgCaptureWorkerChoice[]
          }>('/org/capture/jitsi')
        : Promise.resolve(null),
    ]
    const [o, u, tr, ssoConfig, captureConfig] = await Promise.all(requests)
    setOrg(o)
    setName(o.name)
    setTtl(o.password_ttl_days)
    setMfaRequired(o.mfa_required)
    setAllowPublicLinks(o.allow_public_links)
    setTariffId(tariffSelectable(tr.items, o.tariff) ? o.tariff.id : '')
    setUsers(u.items)
    setTariffs(tr.items)
    if (ssoConfig) {
      setSso(ssoConfig)
      setSsoIssuer(ssoConfig.issuer || '')
      setSsoClientId(ssoConfig.client_id || '')
      setSsoEnabled(ssoConfig.enabled)
      setSsoClientSecret('')
    }
    if (captureConfig) {
      setCaptureAllowed(captureConfig.allowed)
      setCaptureBotDisplayName(captureConfig.bot_display_name ?? '')
      setCaptureHosts(captureConfig.items)
      setCaptureWorkers(captureConfig.workers ?? [])
    }
  }

  function captureHostPayloadRow(row: OrgCaptureJitsiHost) {
    return {
      id: row.id,
      host: row.host,
      jwt_app_id: row.jwt_app_id ?? null,
    }
  }

  async function putCaptureHostItems(items: Record<string, unknown>[]) {
    const result = await api<{
      bot_display_name?: string
      items: OrgCaptureJitsiHost[]
      workers: OrgCaptureWorkerChoice[]
    }>('/org/capture/jitsi', {
      method: 'PUT',
      body: JSON.stringify({ items, bot_display_name: captureBotDisplayName }),
    })
    setCaptureBotDisplayName(result.bot_display_name ?? '')
    setCaptureHosts(result.items)
    setCaptureWorkers(result.workers ?? [])
  }

  async function saveCaptureBotDisplayName() {
    const result = await api<{
      bot_display_name?: string
      items: OrgCaptureJitsiHost[]
      workers: OrgCaptureWorkerChoice[]
    }>('/org/capture/jitsi', {
      method: 'PUT',
      body: JSON.stringify({
        items: captureHosts.map((row) => captureHostPayloadRow(row)),
        bot_display_name: captureBotDisplayName,
      }),
    })
    setCaptureBotDisplayName(result.bot_display_name ?? '')
    setCaptureHosts(result.items)
    setCaptureWorkers(result.workers ?? [])
  }

  async function saveCaptureHosts(nextItems: OrgCaptureJitsiHost[]) {
    await putCaptureHostItems(nextItems.map((row) => captureHostPayloadRow(row)))
  }

  function resetCaptureDraft() {
    setCaptureEditingId(null)
    setCaptureDraft({ host: '', jwt_app_id: '', jwt_secret: '', clear_jwt_secret: false })
  }

  function startEditCaptureHost(row: OrgCaptureJitsiHost) {
    setCaptureEditingId(row.id)
    setCaptureDraft({
      host: row.host,
      jwt_app_id: row.jwt_app_id || '',
      jwt_secret: '',
      clear_jwt_secret: false,
    })
  }

  async function submitCaptureDraft() {
    const host = normalizeJitsiHostInput(captureDraft.host)
    if (!host) return

    const draftFields: Record<string, unknown> = {
      host,
      jwt_app_id: captureDraft.jwt_app_id.trim() || null,
    }
    if (captureDraft.jwt_secret.trim()) {
      draftFields.jwt_secret = captureDraft.jwt_secret.trim()
    }
    if (captureDraft.clear_jwt_secret) {
      draftFields.clear_jwt_secret = true
    }

    const items: Record<string, unknown>[] = captureEditingId
      ? captureHosts.map((row) =>
          row.id === captureEditingId ? { id: row.id, ...draftFields } : captureHostPayloadRow(row),
        )
      : [...captureHosts.map((row) => captureHostPayloadRow(row)), draftFields]

    await putCaptureHostItems(items)
    resetCaptureDraft()
  }

  async function removeCaptureHost(row: OrgCaptureJitsiHost) {
    if (captureEditingId === row.id) resetCaptureDraft()
    const next = captureHosts.filter((item) => item.id !== row.id)
    await saveCaptureHosts(next)
  }

  useEffect(() => {
    if (!hasOrg) return
    load().catch(showError)
  }, [hasOrg])

  if (!hasOrg) return <Navigate to="/app/profile" replace />

  const currentTariff = org?.tariff ?? null
  const currentSelectable = currentTariff ? tariffSelectable(tariffs, currentTariff) : false
  const selectedTariff = tariffId ? tariffs.find((tr) => tr.id === tariffId) ?? null : null
  const canSaveTariff = Boolean(
    admin && selectedTariff && currentTariff && tariffId !== currentTariff.id,
  )
  const profileDirty = Boolean(
    org
    && (
      name.trim() !== org.name
      || ttl !== org.password_ttl_days
      || mfaRequired !== org.mfa_required
      || allowPublicLinks !== org.allow_public_links
    ),
  )
  const ssoBlocksMfa = Boolean(sso?.enabled)

  async function saveProfile() {
    if (!org) return
    const tasks: Promise<unknown>[] = []
    const trimmed = name.trim()
    if (trimmed && trimmed !== org.name) {
      tasks.push(api('/org', { method: 'PATCH', body: JSON.stringify({ name: trimmed }) }))
    }
    const settingsPatch: { password_ttl_days?: number; mfa_required?: boolean; allow_public_links?: boolean } = {}
    if (ttl !== org.password_ttl_days) settingsPatch.password_ttl_days = ttl
    if (mfaRequired !== org.mfa_required) settingsPatch.mfa_required = mfaRequired
    if (allowPublicLinks !== org.allow_public_links) settingsPatch.allow_public_links = allowPublicLinks
    if (Object.keys(settingsPatch).length > 0) {
      tasks.push(api('/org/settings', { method: 'PATCH', body: JSON.stringify(settingsPatch) }))
    }
    if (tasks.length === 0) return
    await Promise.all(tasks)
    if (trimmed && trimmed !== org.name) await refresh()
    await load()
  }

  async function saveSso() {
    const body: Record<string, unknown> = {
      issuer: ssoIssuer,
      client_id: ssoClientId,
      enabled: ssoEnabled,
    }
    if (ssoClientSecret.trim()) body.client_secret = ssoClientSecret
    await api('/org/sso', { method: 'PATCH', body: JSON.stringify(body) })
    setSsoClientSecret('')
    await load()
  }

  async function saveTariff() {
    if (!canSaveTariff) return
    try {
      await api('/org/tariff', { method: 'PATCH', body: JSON.stringify({ tariff_id: tariffId }) })
      await refresh()
      await load()
    } catch (e) {
      showError(e)
    }
  }

  function ensureUserPassword(current = password) {
    if (current) return current
    return randomPassword()
  }

  async function copyAddUserPassword() {
    if (!password) return
    try {
      await navigator.clipboard.writeText(password)
      setCopiedAddUserPassword(true)
      window.setTimeout(() => setCopiedAddUserPassword(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  async function addUser() {
    const pw = ensureUserPassword()
    if (!password) setPassword(pw)
    try {
      await api('/org/users', { method: 'POST', body: JSON.stringify({ email, password: pw, role }) })
      setEmail('')
      setPassword('')
      await load()
    } catch (e) {
      showError(e)
    }
  }

  async function changeRole(user: User, next: string) {
    await api(`/org/users/${user.id}`, { method: 'PATCH', body: JSON.stringify({ role: next }) })
    await load()
  }

  async function toggleDisabled(user: User) {
    await api(`/org/users/${user.id}/${user.disabled ? 'enable' : 'disable'}`, { method: 'POST' })
    await load()
  }

  async function copyResetPassword() {
    if (!tempPw) return
    try {
      await navigator.clipboard.writeText(tempPw.password)
      setCopiedResetPassword(true)
      window.setTimeout(() => setCopiedResetPassword(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  async function resetPw(user: User) {
    try {
      const r = await api<{ password: string }>(`/org/users/${user.id}/reset-password`, { method: 'POST' })
      setTempPw({ email: user.email, password: r.password })
      setMfaResetOk(null)
      await load()
    } catch (e) {
      showError(e)
    }
  }

  async function confirmResetMfa() {
    if (!mfaResetUser) return
    setMfaResetBusy(true)
    try {
      await api(`/org/users/${mfaResetUser.id}/reset-mfa`, { method: 'POST' })
      setMfaResetOk(mfaResetUser.email)
      setTempPw(null)
      setMfaResetUser(null)
      await load()
    } catch (e) {
      showError(e)
      await load()
    } finally {
      setMfaResetBusy(false)
    }
  }

  async function offboard() {
    if (!offUser) return
    try {
      await api(`/org/users/${offUser.id}/offboard`, {
        method: 'POST',
        body: JSON.stringify({ action, target_user_id: action === 'transfer' ? target : undefined }),
      })
      setOffUser(null)
      await load()
    } catch (e) {
      showError(e)
    }
  }

  return (
    <AdminPage>
      {org && (
        <>
          <StatGrid>
            <StatCard label={t('org.kpiMembers')} value={formatInteger(summary.total)} tone="ops" />
            <StatCard label={t('org.kpiActive')} value={formatInteger(summary.active)} tone="transcribe" />
            <StatCard label={t('org.kpiAdmins')} value={formatInteger(summary.admins)} tone="summarize" />
            <StatCard
              label={t('wallet.balance')}
              value={org.unlimited ? t('wallet.unlimited') : formatDecimal(org.balance)}
              tone="amount"
            />
          </StatGrid>
          <div className="org-settings-stack">
          <AdminFormCard title={t('org.profile')}>
            <label>
              {t('common.name')}
              <input value={name} disabled={!admin} onChange={(e) => setName(e.target.value)} />
            </label>
            <label>
              {t('org.ttl')}
              <input type="number" min={0} value={ttl} disabled={!admin} onChange={(e) => setTtl(Number(e.target.value))} />
            </label>
            {admin && (
              <label className="profile-check-row">
                <input
                  type="checkbox"
                  checked={mfaRequired}
                  disabled={ssoBlocksMfa}
                  onChange={(e) => setMfaRequired(e.target.checked)}
                />
                {t('org.mfaRequired')}
              </label>
            )}
            {admin && ssoBlocksMfa && (
              <p className="muted">{t('org.mfaRequiredSsoHint')}</p>
            )}
            {admin && (
              <label className="profile-check-row">
                <input
                  type="checkbox"
                  checked={allowPublicLinks}
                  onChange={(e) => setAllowPublicLinks(e.target.checked)}
                />
                {t('org.allowPublicLinks')}
              </label>
            )}
            {admin && !allowPublicLinks && (
              <p className="muted">{t('org.allowPublicLinksHint')}</p>
            )}
            {admin && (
              <p className="muted">
                <Link to="/app/public-links">{t('publicLinks.manage')}</Link>
              </p>
            )}
            {admin && (
              <button
                className="primary"
                type="button"
                disabled={!profileDirty}
                onClick={() => void saveProfile().catch(showError)}
              >
                {t('common.save')}
              </button>
            )}
          </AdminFormCard>
          <details className="fold org-fold org-tariff-fold card">
            <summary className="org-fold-summary">
              <span>{t('org.tariff')}</span>
              {currentTariff && (
                <span className="row">
                  <span className="badge">{currentTariff.name}</span>
                  {org.unlimited ? (
                    <span className="badge out">{t('wallet.unlimited')}</span>
                  ) : (
                    <span className="org-balance">{org.balance}</span>
                  )}
                  {currentTariff.archived && <span className="badge warn">{t('instance.archived')}</span>}
                </span>
              )}
            </summary>
            <div className="stack fold-body">
              <WalletLabel unlimited={org.unlimited} balance={org.balance} />
              {!admin && currentTariff && (
                <>
                  <div className="row">
                    <strong className="grow">{t('org.tariffCurrent')}: {currentTariff.name}</strong>
                    {currentTariff.unlimited && <span className="badge">{t('wallet.unlimited')}</span>}
                    {currentTariff.archived && <span className="badge warn">{t('instance.archived')}</span>}
                  </div>
                  <TariffDetails tariff={currentTariff} />
                </>
              )}
              {admin && currentTariff && !currentSelectable && (
                <>
                  <div className="row">
                    <strong className="grow">{t('org.tariffCurrent')}: {currentTariff.name}</strong>
                    {currentTariff.unlimited && <span className="badge">{t('wallet.unlimited')}</span>}
                    {currentTariff.archived && <span className="badge warn">{t('instance.archived')}</span>}
                  </div>
                  <TariffDetails tariff={currentTariff} />
                  <p className="muted">{t('org.tariffLegacy')}</p>
                </>
              )}
              {admin && tariffs.length > 0 && (
                <label>
                  {currentSelectable ? t('org.tariff') : t('org.tariffSwitch')}
                  <select value={tariffId} onChange={(e) => setTariffId(e.target.value)}>
                    {!currentSelectable && <option value="">—</option>}
                    {tariffs.map((tr) => (
                      <option key={tr.id} value={tr.id}>
                        {tr.name}{tr.unlimited ? ` (${t('wallet.unlimited')})` : ''}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {admin && selectedTariff && currentSelectable && (
                <TariffDetails tariff={selectedTariff} />
              )}
              {admin && selectedTariff && currentTariff && !currentSelectable && selectedTariff.id !== currentTariff.id && (
                <>
                  <div className="row">
                    <strong className="grow">{t('org.tariffSwitch')}: {selectedTariff.name}</strong>
                    {selectedTariff.unlimited && <span className="badge">{t('wallet.unlimited')}</span>}
                  </div>
                  <TariffDetails tariff={selectedTariff} />
                </>
              )}
              {admin && (
                <button className="primary" type="button" disabled={!canSaveTariff} onClick={() => void saveTariff()}>
                  {t('common.save')}
                </button>
              )}
            </div>
          </details>
          {admin && hasOrg && (
            <details className="fold org-fold card">
              <summary className="org-fold-summary">
                <span>{t('org.captureJitsiTitle')}</span>
                {captureAllowed && <span className="badge out">{t('org.captureEnabled')}</span>}
              </summary>
              <div className="stack fold-body">
                {!captureAllowed ? (
                  <p className="muted">{t('org.captureDisabledHint')}</p>
                ) : (
                  <>
                    <p className="muted">{t('org.captureJitsiHint')}</p>
                    <div className="stack">
                      <label>
                        {t('org.captureBotDisplayName')}
                        <input
                          value={captureBotDisplayName}
                          maxLength={128}
                          placeholder={t('org.captureBotDisplayNameDefault')}
                          onChange={(e) => setCaptureBotDisplayName(e.target.value)}
                        />
                      </label>
                      <p className="muted">{t('org.captureBotDisplayNameHint')}</p>
                      <button type="button" className="primary" onClick={() => void saveCaptureBotDisplayName().catch(showError)}>
                        {t('common.save')}
                      </button>
                    </div>
                    {captureWorkers.length === 0 ? (
                      <p className="err">{t('org.captureNoWorkers')}</p>
                    ) : null}
                    {captureHosts.length > 0 ? (
                      <div className="stats-table-wrap">
                        <table className="stats-table">
                          <thead>
                            <tr>
                              <th>{t('org.captureHost')}</th>
                              <th>{t('org.captureJwtAppId')}</th>
                              <th>{t('org.captureJwtSecret')}</th>
                              <th />
                            </tr>
                          </thead>
                          <tbody>
                            {captureHosts.map((row) => (
                              <tr key={row.id}>
                                <td>{row.host}</td>
                                <td>{row.jwt_app_id ?? 'chat'}</td>
                                <td>{row.jwt_secret_configured ? t('org.captureJwtSaved') : '—'}</td>
                                <td className="table-actions">
                                  <button
                                    type="button"
                                    disabled={captureEditingId === row.id}
                                    onClick={() => startEditCaptureHost(row)}
                                  >
                                    {t('common.edit')}
                                  </button>
                                  <button type="button" className="danger" onClick={() => void removeCaptureHost(row).catch(showError)}>
                                    {t('common.delete')}
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="muted">{t('common.empty')}</p>
                    )}
                    <div className="stack">
                      {captureEditingId ? (
                        <p className="muted">{t('org.captureEditHost')}</p>
                      ) : null}
                      <label>
                        {t('org.captureHost')}
                        <input
                          value={captureDraft.host}
                          placeholder="https://meet..."
                          onChange={(e) => setCaptureDraft({ ...captureDraft, host: e.target.value })}
                        />
                      </label>
                      <p className="muted">{t('org.captureHostHint')}</p>
                      <label>
                        {t('org.captureJwtAppId')}
                        <input
                          value={captureDraft.jwt_app_id}
                          placeholder="chat"
                          onChange={(e) => setCaptureDraft({ ...captureDraft, jwt_app_id: e.target.value })}
                        />
                      </label>
                      <label>
                        {t('org.captureJwtSecret')}
                        <input
                          type="password"
                          value={captureDraft.jwt_secret}
                          autoComplete="off"
                          placeholder={
                            captureEditingId &&
                            captureHosts.find((row) => row.id === captureEditingId)?.jwt_secret_configured
                              ? t('org.captureJwtSecretKeepHint')
                              : undefined
                          }
                          onChange={(e) => setCaptureDraft({ ...captureDraft, jwt_secret: e.target.value })}
                        />
                      </label>
                      {captureEditingId &&
                      captureHosts.find((row) => row.id === captureEditingId)?.jwt_secret_configured ? (
                        <label className="row">
                          <input
                            type="checkbox"
                            checked={captureDraft.clear_jwt_secret}
                            onChange={(e) =>
                              setCaptureDraft({ ...captureDraft, clear_jwt_secret: e.target.checked })
                            }
                          />
                          {t('org.captureClearJwtSecret')}
                        </label>
                      ) : null}
                      <div className="row">
                        <button
                          type="button"
                          className="primary"
                          disabled={
                            !normalizeJitsiHostInput(captureDraft.host) ||
                            captureWorkers.length === 0
                          }
                          onClick={() => void submitCaptureDraft().catch(showError)}
                        >
                          {captureEditingId ? t('common.save') : t('org.captureAddHost')}
                        </button>
                        {captureEditingId ? (
                          <button type="button" onClick={resetCaptureDraft}>
                            {t('common.cancel')}
                          </button>
                        ) : null}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </details>
          )}
          {canConfigureSso && (
            <details className="fold org-fold org-sso-fold card">
              <summary className="org-fold-summary">
                <span>{t('sso.settingsTitle')}</span>
                {sso && (
                  <span className="row">
                    {sso.enabled && <span className="badge out">{t('sso.enabled')}</span>}
                    {!sso.enabled && sso.configured && <span className="badge">{t('sso.configured')}</span>}
                  </span>
                )}
              </summary>
              <div className="sso-card stack fold-body">
                <p className="muted sso-lead">{t('sso.settingsLead')}</p>
                {sso && (
                  <>
                    <div className="sso-ref">
                      <SsoUrlRow label={t('sso.orgId')} value={sso.org_id} />
                    </div>
                    <p className="muted sso-lead">{t('sso.orgIdHint')}</p>
                    {sso.public_base_url_set && sso.login_url && sso.callback_url ? (
                      <div className="sso-ref">
                        <SsoUrlRow label={t('sso.callbackUrl')} value={sso.callback_url} />
                        <SsoUrlRow label={t('sso.loginUrl')} value={sso.login_url} />
                      </div>
                    ) : (
                      <p className="err sso-lead">{t('sso.publicBaseUrlMissing')}</p>
                    )}
                  </>
                )}
                <div className="sso-fields">
                  <label>
                    {t('sso.issuer')}
                    <input value={ssoIssuer} onChange={(e) => setSsoIssuer(e.target.value)} placeholder="https://keycloak.example/realms/myrealm" />
                  </label>
                  <div className="sso-field-row">
                    <label>
                      {t('sso.clientId')}
                      <input value={ssoClientId} onChange={(e) => setSsoClientId(e.target.value)} />
                    </label>
                    <label>
                      {t('sso.clientSecret')}
                      <input
                        type="password"
                        value={ssoClientSecret}
                        onChange={(e) => setSsoClientSecret(e.target.value)}
                        placeholder={sso?.has_client_secret ? t('sso.secretSaved') : ''}
                      />
                    </label>
                  </div>
                </div>
                <div className="sso-actions">
                  <label className="inline">
                    <input type="checkbox" checked={ssoEnabled} onChange={(e) => setSsoEnabled(e.target.checked)} />
                    <span>{t('sso.enabled')}</span>
                  </label>
                  <button className="primary" type="button" onClick={() => void saveSso().catch(showError)}>
                    {t('common.save')}
                  </button>
                </div>
              </div>
            </details>
          )}
          </div>
        </>
      )}
      {mfaResetOk && (
        <p className="ok admin-notice">{t('org.resetMfaDone')} ({mfaResetOk})</p>
      )}
      {admin && (
        <details
          className="fold org-fold org-add-user-fold card"
          onToggle={(e) => {
            if (e.currentTarget.open && !password) setPassword(randomPassword())
          }}
        >
          <summary className="org-fold-summary">
            <span>{t('org.addUser')}</span>
          </summary>
          <div className="stack fold-body">
            <label>
              {t('common.email')}
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              {t('common.password')}
              <div className="public-link-actions-row">
                <div className="public-link-url-row">
                  <code className="public-link-url" title={password}>
                    {password || '—'}
                  </code>
                  <button
                    type="button"
                    className="public-link-copy"
                    disabled={!password}
                    onClick={() => void copyAddUserPassword()}
                  >
                    {copiedAddUserPassword ? t('profile.copied') : t('common.copy')}
                  </button>
                </div>
                <button
                  type="button"
                  className="public-link-revoke"
                  onClick={() => setPassword(randomPassword())}
                >
                  {t('instance.orgGeneratePassword')}
                </button>
              </div>
            </label>
            <label>
              {t('common.role')}
              <select value={role} onChange={(e) => setRole(e.target.value as 'org_admin' | 'org_member')}>
                <option value="org_member">{t('org.roleMember')}</option>
                <option value="org_admin">{t('org.roleAdmin')}</option>
              </select>
            </label>
            <button className="primary" type="button" onClick={() => void addUser()}>{t('common.create')}</button>
          </div>
        </details>
      )}
      <AdminTableCard title={t('org.people')} empty={t('common.empty')} isEmpty={users.length === 0}>
        <div className="stats-table-wrap">
          <table className="stats-table">
            <thead>
              <tr>
                <th>{t('common.email')}</th>
                <th>{t('common.role')}</th>
                <th>{t('common.status')}</th>
                {admin && <th>{t('common.actions')}</th>}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>
                    {admin ? (
                      <select value={u.role || 'org_member'} onChange={(e) => void changeRole(u, e.target.value)}>
                        <option value="org_member">{t('org.roleMember')}</option>
                        <option value="org_admin">{t('org.roleAdmin')}</option>
                      </select>
                    ) : (
                      <span className="badge">
                        {u.role === 'org_admin' ? t('org.roleAdmin') : t('org.roleMember')}
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="row wrap">
                      {!u.disabled &&
                      u.user_agreement_status !== 'pending' &&
                      u.user_agreement_status !== 'accepted' ? (
                        <span className="badge out">{t('org.statusActive')}</span>
                      ) : null}
                      <UserStatusBadges user={u} />
                    </div>
                  </td>
                  {admin && (
                    <td>
                      <div className="row">
                        {u.id !== me?.user.id && !u.disabled && (
                          <button
                            type="button"
                            onClick={() =>
                              void api('/impersonate', {
                                method: 'POST',
                                body: JSON.stringify({ user_id: u.id }),
                              })
                                .then(() => refresh())
                                .then(() => nav(LIBRARY_DEFAULT))
                                .catch(showError)
                            }
                          >
                            {t('org.impersonate')}
                          </button>
                        )}
                        <button type="button" onClick={() => void toggleDisabled(u)}>
                          {u.disabled ? t('common.enable') : t('common.disable')}
                        </button>
                        <button type="button" onClick={() => void resetPw(u)}>{t('org.resetPassword')}</button>
                        {canAdminResetMemberMfa(u, { ssoBlocksMfa, allowInstanceAdmin: true }) ? (
                          <button type="button" onClick={() => setMfaResetUser(u)}>{t('org.resetMfa')}</button>
                        ) : null}
                        <button type="button" className="danger" onClick={() => setOffUser(u)}>{t('org.offboard')}</button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AdminTableCard>
      {tempPw && (
        <Modal onClose={() => setTempPw(null)} panelClassName="stack">
          <h2>{t('org.resetPassword')}</h2>
          <p>{t('org.newPassword')} ({tempPw.email})</p>
          <div className="public-link-actions-row">
            <div className="public-link-url-row">
              <code className="public-link-url" title={tempPw.password}>{tempPw.password}</code>
              <button
                type="button"
                className="public-link-copy"
                onClick={() => void copyResetPassword()}
              >
                {copiedResetPassword ? t('profile.copied') : t('common.copy')}
              </button>
            </div>
          </div>
          <div className="row modal-actions">
            <button type="button" onClick={() => setTempPw(null)}>{t('common.close')}</button>
          </div>
        </Modal>
      )}
      {mfaResetUser && (
        <ConfirmDialog
          message={t('org.resetMfaConfirm', { email: mfaResetUser.email })}
          confirmLabel={t('org.resetMfa')}
          danger
          busy={mfaResetBusy}
          onConfirm={() => void confirmResetMfa()}
          onClose={() => setMfaResetUser(null)}
        />
      )}
      {offUser && (
        <Modal onClose={() => setOffUser(null)} panelClassName="stack">
          <h2>{t('org.offboard')}: {offUser.email}</h2>
          <label>
            <select value={action} onChange={(e) => setAction(e.target.value as 'transfer' | 'wipe')}>
              <option value="wipe">{t('org.wipe')}</option>
              <option value="transfer">{t('org.transfer')}</option>
            </select>
          </label>
          {action === 'transfer' && (
            <label>
              {t('org.target')}
              <select value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="">—</option>
                {users.filter((u) => u.id !== offUser.id && !u.disabled).map((u) => (
                  <option key={u.id} value={u.id}>{u.email}</option>
                ))}
              </select>
            </label>
          )}
          <div className="row modal-actions">
            <button className="danger" type="button" onClick={() => void offboard()}>{t('common.confirm')}</button>
            <button type="button" onClick={() => setOffUser(null)}>{t('common.cancel')}</button>
          </div>
        </Modal>
      )}
    </AdminPage>
  )
}
