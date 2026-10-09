import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import type {
  SchemaOrgCaptureJitsiResponse,
  SchemaOrgPublicResponse,
  SchemaOrgUserListResponse,
  SchemaOrgUserResetPasswordResponse,
  SchemaOrgSsoAdminResponse,
  SchemaTariffListResponse,
} from '../openapi'
import { isOrgAdmin, useAuth } from '../auth'
import { AdminFormCard, AdminPage, AdminTableCard } from '../components/AdminSection'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Modal } from '../components/Modal'
import { StatCard, StatGrid } from '../components/StatCard'
import { TariffDetails } from '../components/TariffDetails'
import { UserStatusBadges } from '../components/UserAgreementBadge'
import { LIBRARY_DEFAULT, libraryPath } from '../routes'
import type { Org, OrgCaptureJitsiHost, OrgCaptureWorkerChoice, Tariff, User } from '../types'
import { normalizeJitsiHostInput } from '../util/captureHost'
import { formatDecimal, formatInteger, showError, WalletLabel } from '../util'
import { canAdminResetMemberMfa } from '../mfa'
import { randomPassword } from '../util/password'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  AdminDataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  adminTableCellActions,
  adminTableCellBadges,
  adminTableCellPrimary,
  adminTableHeadActions,
} from '../components/app/AdminDataTable'
import { AdminRowActions, HubBadge } from '../components/app/AdminUi'
import { AppSelect } from '../components/app/AppSelect'
import { AppCheckboxRow, AppInputField, AppSelectField } from '../components/app/AppFormControls'
import { AppField } from '../components/app/AppField'
import { AdminFormActions, AppSubmitButton } from '../components/app/AdminUi'
import { SettingsFoldSummary } from '../components/app/SettingsFoldSummary'
import { AppUrlCopyRow } from '../components/app/AppUrlCopyRow'

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
  const [mfaResetOk, setMfaResetOk] = useState<string | null>(null)
  const [mfaResetUser, setMfaResetUser] = useState<User | null>(null)
  const [mfaResetBusy, setMfaResetBusy] = useState(false)
  const [sso, setSso] = useState<SchemaOrgSsoAdminResponse | null>(null)
  const [ssoIssuer, setSsoIssuer] = useState('')
  const [ssoClientId, setSsoClientId] = useState('')
  const [ssoClientSecret, setSsoClientSecret] = useState('')
  const [ssoEnabled, setSsoEnabled] = useState(false)
  const [captureAllowed, setCaptureAllowed] = useState(false)
  const [captureBotDisplayName, setCaptureBotDisplayName] = useState('')
  const [savedCaptureBotName, setSavedCaptureBotName] = useState('')
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
      Promise<SchemaOrgPublicResponse>,
      Promise<SchemaOrgUserListResponse>,
      Promise<SchemaTariffListResponse>,
      Promise<SchemaOrgSsoAdminResponse> | Promise<null>,
      Promise<SchemaOrgCaptureJitsiResponse> | Promise<null>,
    ] = [
      api<SchemaOrgPublicResponse>('/org'),
      api<SchemaOrgUserListResponse>('/org/users'),
      api<SchemaTariffListResponse>('/org/available-tariffs'),
      admin && hasOrg ? api<SchemaOrgSsoAdminResponse>('/org/sso') : Promise.resolve(null),
      admin && hasOrg ? api<SchemaOrgCaptureJitsiResponse>('/org/capture/jitsi') : Promise.resolve(null),
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
      setCaptureAllowed(Boolean(captureConfig.allowed))
      const botName = captureConfig.bot_display_name ?? ''
      setCaptureBotDisplayName(botName)
      setSavedCaptureBotName(botName)
      setCaptureHosts(
        (captureConfig.items ?? []).map((row) => ({
          ...row,
          jwt_app_id: row.jwt_app_id ?? null,
        })),
      )
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
    const botName = result.bot_display_name ?? ''
    setCaptureBotDisplayName(botName)
    setSavedCaptureBotName(botName)
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
    const botName = result.bot_display_name ?? ''
    setCaptureBotDisplayName(botName)
    setSavedCaptureBotName(botName)
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
  const captureBotDirty = captureBotDisplayName.trim() !== savedCaptureBotName.trim()
  const captureDraftReady = useMemo(() => {
    if (captureWorkers.length === 0) return false
    const host = normalizeJitsiHostInput(captureDraft.host)
    if (!host) return false
    if (!captureEditingId) return true
    const row = captureHosts.find((r) => r.id === captureEditingId)
    if (!row) return false
    if (host !== row.host) return true
    if ((captureDraft.jwt_app_id.trim() || '') !== (row.jwt_app_id || '').trim()) return true
    if (captureDraft.jwt_secret.trim().length > 0) return true
    if (captureDraft.clear_jwt_secret) return true
    return false
  }, [captureDraft, captureEditingId, captureHosts, captureWorkers.length])
  const ssoDirty = useMemo(() => {
    if (!sso) return false
    return (
      ssoIssuer.trim() !== (sso.issuer || '').trim()
      || ssoClientId.trim() !== (sso.client_id || '').trim()
      || ssoEnabled !== sso.enabled
      || ssoClientSecret.trim().length > 0
    )
  }, [sso, ssoIssuer, ssoClientId, ssoEnabled, ssoClientSecret])
  const canAddUser = useMemo(() => {
    const trimmed = email.trim()
    return trimmed.length > 0 && trimmed.includes('@')
  }, [email])
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

  async function resetPw(user: User) {
    try {
      const r = await api<SchemaOrgUserResetPasswordResponse>(`/org/users/${user.id}/reset-password`, {
        method: 'POST',
      })
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
            <AppInputField
              label={t('common.name')}
              htmlFor="org-profile-name"
              value={name}
              disabled={!admin}
              onChange={(e) => setName(e.target.value)}
            />
            <AppInputField
              label={t('org.ttl')}
              htmlFor="org-profile-ttl"
              type="number"
              min={0}
              value={ttl}
              disabled={!admin}
              onChange={(e) => setTtl(Number(e.target.value))}
            />
            {admin && (
              <AppCheckboxRow
                id="org-mfa-required"
                label={t('org.mfaRequired')}
                checked={mfaRequired}
                disabled={ssoBlocksMfa}
                onCheckedChange={setMfaRequired}
              />
            )}
            {admin && ssoBlocksMfa && (
              <p className="muted">{t('org.mfaRequiredSsoHint')}</p>
            )}
            {admin && (
              <AppCheckboxRow
                id="org-allow-public-links"
                label={t('org.allowPublicLinks')}
                checked={allowPublicLinks}
                onCheckedChange={setAllowPublicLinks}
              />
            )}
            {admin && !allowPublicLinks && (
              <p className="muted">{t('org.allowPublicLinksHint')}</p>
            )}
            {admin && (
              <p className="muted">
                <Link to={libraryPath('links')}>{t('publicLinks.manage')}</Link>
              </p>
            )}
            {admin ? (
              <AdminFormActions>
                <AppSubmitButton ready={profileDirty} onClick={() => void saveProfile().catch(showError)}>
                  {t('common.save')}
                </AppSubmitButton>
              </AdminFormActions>
            ) : null}
          </AdminFormCard>
          <Card className="org-settings-folds gap-0 overflow-hidden py-0">
          <details className="fold org-fold-section org-tariff-fold">
            <summary className="org-fold-summary">
              <SettingsFoldSummary
                title={t('org.tariff')}
                meta={
                  currentTariff ? (
                    <>
                      <HubBadge tone="muted">{currentTariff.name}</HubBadge>
                      {org.unlimited ? (
                        <HubBadge tone="success">{t('wallet.unlimited')}</HubBadge>
                      ) : (
                        <span className="org-balance">{org.balance}</span>
                      )}
                      {currentTariff.archived ? <HubBadge tone="pending">{t('instance.archived')}</HubBadge> : null}
                    </>
                  ) : undefined
                }
              />
            </summary>
            <div className="flex flex-col gap-3 fold-body">
              <WalletLabel unlimited={org.unlimited} balance={org.balance} />
              {!admin && currentTariff && (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="grow">{t('org.tariffCurrent')}: {currentTariff.name}</strong>
                    {currentTariff.unlimited ? <HubBadge tone="success">{t('wallet.unlimited')}</HubBadge> : null}
                    {currentTariff.archived ? <HubBadge tone="pending">{t('instance.archived')}</HubBadge> : null}
                  </div>
                  <TariffDetails tariff={currentTariff} />
                </>
              )}
              {admin && currentTariff && !currentSelectable && (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="grow">{t('org.tariffCurrent')}: {currentTariff.name}</strong>
                    {currentTariff.unlimited ? <HubBadge tone="success">{t('wallet.unlimited')}</HubBadge> : null}
                    {currentTariff.archived ? <HubBadge tone="pending">{t('instance.archived')}</HubBadge> : null}
                  </div>
                  <TariffDetails tariff={currentTariff} />
                  <p className="muted">{t('org.tariffLegacy')}</p>
                </>
              )}
              {admin && tariffs.length > 0 && (
                <AppSelectField
                  label={currentSelectable ? t('org.tariff') : t('org.tariffSwitch')}
                  htmlFor="org-tariff-select"
                  value={tariffId}
                  onValueChange={setTariffId}
                  options={[
                    ...(!currentSelectable ? [{ value: '', label: '—' }] : []),
                    ...tariffs.map((tr) => ({
                      value: tr.id,
                      label: `${tr.name}${tr.unlimited ? ` (${t('wallet.unlimited')})` : ''}`,
                    })),
                  ]}
                />
              )}
              {admin && selectedTariff && currentSelectable && (
                <TariffDetails tariff={selectedTariff} />
              )}
              {admin && selectedTariff && currentTariff && !currentSelectable && selectedTariff.id !== currentTariff.id && (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="grow">{t('org.tariffSwitch')}: {selectedTariff.name}</strong>
                    {selectedTariff.unlimited ? <HubBadge tone="success">{t('wallet.unlimited')}</HubBadge> : null}
                  </div>
                  <TariffDetails tariff={selectedTariff} />
                </>
              )}
              {admin ? (
                <AdminFormActions>
                  <AppSubmitButton ready={canSaveTariff} onClick={() => void saveTariff()}>
                    {t('common.save')}
                  </AppSubmitButton>
                </AdminFormActions>
              ) : null}
            </div>
          </details>
          {admin && hasOrg && (
            <details className="fold org-fold-section">
              <summary className="org-fold-summary">
                <SettingsFoldSummary
                  title={t('org.captureJitsiTitle')}
                  meta={
                    captureAllowed ? <HubBadge tone="success">{t('org.captureEnabled')}</HubBadge> : undefined
                  }
                />
              </summary>
              <div className="flex flex-col gap-3 fold-body">
                {!captureAllowed ? (
                  <p className="muted">{t('org.captureDisabledHint')}</p>
                ) : (
                  <>
                    <p className="muted">{t('org.captureJitsiHint')}</p>
                    <div className="flex flex-col gap-3">
                      <AppInputField
                        label={t('org.captureBotDisplayName')}
                        htmlFor="org-capture-bot-name"
                        value={captureBotDisplayName}
                        maxLength={128}
                        placeholder={t('org.captureBotDisplayNameDefault')}
                        onChange={(e) => setCaptureBotDisplayName(e.target.value)}
                        description={t('org.captureBotDisplayNameHint')}
                      />
                      <AdminFormActions>
                        <AppSubmitButton
                          ready={captureBotDirty}
                          onClick={() => void saveCaptureBotDisplayName().catch(showError)}
                        >
                          {t('common.save')}
                        </AppSubmitButton>
                      </AdminFormActions>
                    </div>
                    {captureWorkers.length === 0 ? (
                      <p className="err">{t('org.captureNoWorkers')}</p>
                    ) : null}
                    {captureHosts.length > 0 ? (
                      <AdminDataTable>
                        <TableHeader>
                          <TableRow>
                            <TableHead>{t('org.captureHost')}</TableHead>
                            <TableHead>{t('org.captureJwtAppId')}</TableHead>
                            <TableHead>{t('org.captureJwtSecret')}</TableHead>
                            <TableHead className={adminTableHeadActions} />
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {captureHosts.map((row) => (
                            <TableRow key={row.id}>
                              <TableCell className={adminTableCellPrimary}>{row.host}</TableCell>
                              <TableCell>{row.jwt_app_id ?? 'chat'}</TableCell>
                              <TableCell>{row.jwt_secret_configured ? t('org.captureJwtSaved') : '—'}</TableCell>
                              <TableCell className={adminTableCellActions}>
                                <AdminRowActions>
                                  <Button type="button" size="sm" variant="outline" disabled={captureEditingId === row.id} onClick={() => startEditCaptureHost(row)}>
                                    {t('common.edit')}
                                  </Button>
                                  <Button type="button" size="sm" variant="destructive" onClick={() => void removeCaptureHost(row).catch(showError)}>
                                    {t('common.delete')}
                                  </Button>
                                </AdminRowActions>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </AdminDataTable>
                    ) : (
                      <p className="muted">{t('common.empty')}</p>
                    )}
                    <div className="flex flex-col gap-3">
                      {captureEditingId ? (
                        <p className="muted">{t('org.captureEditHost')}</p>
                      ) : null}
                      <AppInputField
                        label={t('org.captureHost')}
                        htmlFor="org-capture-host"
                        value={captureDraft.host}
                        placeholder="https://meet..."
                        onChange={(e) => setCaptureDraft({ ...captureDraft, host: e.target.value })}
                        description={t('org.captureHostHint')}
                      />
                      <AppInputField
                        label={t('org.captureJwtAppId')}
                        htmlFor="org-capture-jwt-app-id"
                        value={captureDraft.jwt_app_id}
                        placeholder="chat"
                        onChange={(e) => setCaptureDraft({ ...captureDraft, jwt_app_id: e.target.value })}
                      />
                      <AppInputField
                        label={t('org.captureJwtSecret')}
                        htmlFor="org-capture-jwt-secret"
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
                      {captureEditingId &&
                      captureHosts.find((row) => row.id === captureEditingId)?.jwt_secret_configured ? (
                        <AppCheckboxRow
                          id="org-capture-clear-jwt"
                          label={t('org.captureClearJwtSecret')}
                          checked={captureDraft.clear_jwt_secret}
                          onCheckedChange={(checked) =>
                            setCaptureDraft({ ...captureDraft, clear_jwt_secret: checked })
                          }
                        />
                      ) : null}
                      <AdminFormActions>
                        <AppSubmitButton
                          ready={captureDraftReady}
                          onClick={() => void submitCaptureDraft().catch(showError)}
                        >
                          {captureEditingId ? t('common.save') : t('org.captureAddHost')}
                        </AppSubmitButton>
                        {captureEditingId ? (
                          <Button type="button" variant="outline" onClick={resetCaptureDraft}>
                            {t('common.cancel')}
                          </Button>
                        ) : null}
                      </AdminFormActions>
                    </div>
                  </>
                )}
              </div>
            </details>
          )}
          {canConfigureSso && (
            <details className="fold org-fold-section org-sso-fold">
              <summary className="org-fold-summary">
                <SettingsFoldSummary
                  title={t('sso.settingsTitle')}
                  meta={
                    sso ? (
                      <>
                        {sso.enabled ? <HubBadge tone="success">{t('sso.enabled')}</HubBadge> : null}
                        {!sso.enabled && sso.configured ? (
                          <HubBadge tone="muted">{t('sso.configured')}</HubBadge>
                        ) : null}
                      </>
                    ) : undefined
                  }
                />
              </summary>
              <div className="sso-card flex flex-col gap-3 fold-body">
                <p className="muted sso-lead">{t('sso.settingsLead')}</p>
                {sso && (
                  <>
                    <div className="sso-ref">
                      <AppUrlCopyRow label={t('sso.orgId')} value={sso.org_id} />
                    </div>
                    <p className="muted sso-lead">{t('sso.orgIdHint')}</p>
                    {sso.public_base_url_set && sso.login_url && sso.callback_url ? (
                      <div className="sso-ref">
                        <AppUrlCopyRow label={t('sso.callbackUrl')} value={sso.callback_url} />
                        <AppUrlCopyRow label={t('sso.loginUrl')} value={sso.login_url} />
                      </div>
                    ) : (
                      <p className="err sso-lead">{t('sso.publicBaseUrlMissing')}</p>
                    )}
                  </>
                )}
                <div className="sso-fields">
                  <AppInputField
                    label={t('sso.issuer')}
                    htmlFor="org-sso-issuer"
                    value={ssoIssuer}
                    onChange={(e) => setSsoIssuer(e.target.value)}
                    placeholder="https://keycloak.example/realms/myrealm"
                  />
                  <div className="sso-field-row">
                    <AppInputField
                      label={t('sso.clientId')}
                      htmlFor="org-sso-client-id"
                      value={ssoClientId}
                      onChange={(e) => setSsoClientId(e.target.value)}
                    />
                    <AppInputField
                      label={t('sso.clientSecret')}
                      htmlFor="org-sso-client-secret"
                      type="password"
                      value={ssoClientSecret}
                      onChange={(e) => setSsoClientSecret(e.target.value)}
                      placeholder={sso?.has_client_secret ? t('sso.secretSaved') : ''}
                    />
                  </div>
                </div>
                <AppCheckboxRow
                  id="org-sso-enabled"
                  label={t('sso.enabled')}
                  checked={ssoEnabled}
                  onCheckedChange={setSsoEnabled}
                />
                <AdminFormActions>
                  <AppSubmitButton ready={ssoDirty} onClick={() => void saveSso().catch(showError)}>
                    {t('common.save')}
                  </AppSubmitButton>
                </AdminFormActions>
              </div>
            </details>
          )}
          {admin && (
        <details
          className="fold org-fold-section org-add-user-fold"
          onToggle={(e) => {
            if (e.currentTarget.open && !password) setPassword(randomPassword())
          }}
        >
          <summary className="org-fold-summary">
            <SettingsFoldSummary title={t('org.addUser')} />
          </summary>
          <div className="flex flex-col gap-3 fold-body">
            <AppInputField
              label={t('common.email')}
              htmlFor="org-add-user-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <AppField label={t('common.password')} htmlFor="org-add-user-password">
              <div className="public-link-actions-row">
                <AppUrlCopyRow value={password} id="org-add-user-password" />
                <Button
                  type="button"
                  variant="outline"
                  className="public-link-revoke"
                  onClick={() => setPassword(randomPassword())}
                >
                  {t('instance.orgGeneratePassword')}
                </Button>
              </div>
            </AppField>
            <AppSelectField
              label={t('common.role')}
              htmlFor="org-add-user-role"
              value={role}
              onValueChange={(next) => setRole(next as 'org_admin' | 'org_member')}
              options={[
                { value: 'org_member', label: t('org.roleMember') },
                { value: 'org_admin', label: t('org.roleAdmin') },
              ]}
            />
            <AdminFormActions>
              <AppSubmitButton ready={canAddUser} onClick={() => void addUser()}>
                {t('common.create')}
              </AppSubmitButton>
            </AdminFormActions>
          </div>
        </details>
          )}
          </Card>
          </div>
        </>
      )}
      {mfaResetOk && (
        <p className="ok admin-notice">{t('org.resetMfaDone')} ({mfaResetOk})</p>
      )}
      <AdminTableCard
        title={t('org.people')}
        empty={t('common.empty')}
        isEmpty={users.length === 0}
        tableLayout={users.length > 0}
      >
        {users.length > 0 ? (
          <AdminDataTable>
            <TableHeader>
              <TableRow>
                <TableHead>{t('common.email')}</TableHead>
                <TableHead>{t('common.role')}</TableHead>
                <TableHead>{t('common.status')}</TableHead>
                {admin ? <TableHead className={adminTableHeadActions}>{t('common.actions')}</TableHead> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className={adminTableCellPrimary}>{u.email}</TableCell>
                  <TableCell>
                    {admin ? (
                      <AppSelect
                        className="h-8 min-w-[8rem]"
                        value={u.role || 'org_member'}
                        onValueChange={(next) => void changeRole(u, next)}
                        options={[
                          { value: 'org_member', label: t('org.roleMember') },
                          { value: 'org_admin', label: t('org.roleAdmin') },
                        ]}
                      />
                    ) : (
                      <HubBadge tone="muted">
                        {u.role === 'org_admin' ? t('org.roleAdmin') : t('org.roleMember')}
                      </HubBadge>
                    )}
                  </TableCell>
                  <TableCell className={adminTableCellBadges}>
                    {!u.disabled &&
                    u.user_agreement_status !== 'pending' &&
                    u.user_agreement_status !== 'accepted' ? (
                      <HubBadge tone="success">{t('org.statusActive')}</HubBadge>
                    ) : null}
                    <UserStatusBadges user={u} />
                  </TableCell>
                  {admin ? (
                    <TableCell className={adminTableCellActions}>
                      <AdminRowActions>
                        {u.id !== me?.user.id && !u.disabled ? (
                          <Button type="button" size="sm" variant="outline" onClick={() =>
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
                          </Button>
                        ) : null}
                        <Button type="button" size="sm" variant="outline" onClick={() => void toggleDisabled(u)}>
                          {u.disabled ? t('common.enable') : t('common.disable')}
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => void resetPw(u)}>
                          {t('org.resetPassword')}
                        </Button>
                        {canAdminResetMemberMfa(u, { ssoBlocksMfa, allowInstanceAdmin: true }) ? (
                          <Button type="button" size="sm" variant="outline" onClick={() => setMfaResetUser(u)}>
                            {t('org.resetMfa')}
                          </Button>
                        ) : null}
                        <Button type="button" size="sm" variant="destructive" onClick={() => setOffUser(u)}>
                          {t('org.offboard')}
                        </Button>
                      </AdminRowActions>
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </AdminDataTable>
        ) : null}
      </AdminTableCard>
      {tempPw ? (
        <Modal
          onClose={() => setTempPw(null)}
          title={t('org.resetPassword')}
          description={`${t('org.newPassword')} (${tempPw.email})`}
          footer={
            <Button type="button" onClick={() => setTempPw(null)}>
              {t('common.close')}
            </Button>
          }
        >
          <AppUrlCopyRow value={tempPw.password} />
        </Modal>
      ) : null}
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
          <AppSelectField
            label={t('org.offboard')}
            htmlFor="org-offboard-action"
            value={action}
            onValueChange={(next) => setAction(next as 'transfer' | 'wipe')}
            options={[
              { value: 'wipe', label: t('org.wipe') },
              { value: 'transfer', label: t('org.transfer') },
            ]}
          />
          {action === 'transfer' && (
            <AppSelectField
              label={t('org.target')}
              htmlFor="org-offboard-target"
              value={target}
              onValueChange={setTarget}
              options={[
                { value: '', label: '—' },
                ...users
                  .filter((u) => u.id !== offUser.id && !u.disabled)
                  .map((u) => ({ value: u.id, label: u.email })),
              ]}
            />
          )}
          <div className="flex flex-wrap items-center gap-2 modal-actions">
            <Button variant="destructive" type="button" onClick={() => void offboard()}>{t('common.confirm')}</Button>
            <Button type="button" onClick={() => setOffUser(null)}>{t('common.cancel')}</Button>
          </div>
        </Modal>
      )}
    </AdminPage>
  )
}
