import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { api, apiDownload } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { AdminFormCard, AdminPage, AdminTableCard } from '../components/AdminSection'
import { Modal } from '../components/Modal'
import { MfaSetupPanel } from '../components/MfaSetupPanel'
import { Segmented } from '../components/Segmented'
import { StatCard, StatGrid } from '../components/StatCard'
import {
  allowedDefaultRoutes,
  defaultRouteLabel,
  localAuthProfileVisible,
  normalizeDefaultRoute,
  type DefaultRoute,
} from '../routes'
import type { ApiToken, DateTimeFormatId, DateTimePrefs } from '../types'
import {
  isAvailableSummarizeModel,
  resolveEffectiveSummarizeModel,
} from '../summarizeModels'
import {
  diarizationOptionsForAsr,
  isDispatchableCombo,
  resolveEffectiveAsr,
  resolveEffectiveDiarization,
} from '../transcribeModels'
import { fmtDate, formatInteger, showError } from '../util'
import { DATE_TIME_FORMATS, formatDateTime } from '../util/datetimeFormat'
import { TIMEZONE_OPTIONS } from '../util/timezones'

type AccountDeletePreview = {
  requires_successor: boolean
  will_delete_org: boolean
  candidates: { id: string; email: string; role: string }[]
}

export function ProfilePage() {
  const { t, i18n } = useTranslation()
  const nav = useNavigate()
  const { me, refresh, setDefaultRoute, setDateTimeFormat, setTimezone, setShowOnlyMyItems, logout } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [tokens, setTokens] = useState<ApiToken[]>([])
  const [tokenName, setTokenName] = useState('')
  const [secret, setSecret] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [creating, setCreating] = useState(false)
  const [ok, setOk] = useState(false)
  const [routeOk, setRouteOk] = useState(false)
  const [scopeOk, setScopeOk] = useState(false)
  const [showOnlyMyItems, setShowOnlyMyItemsLocal] = useState(false)
  const [dateTimeOk, setDateTimeOk] = useState(false)
  const [dateTimeFormat, setDateTimeFormatLocal] = useState<'inherit' | DateTimeFormatId>('inherit')
  const [timezone, setTimezoneLocal] = useState<'inherit' | string>('inherit')
  const [asrModel, setAsrModelLocal] = useState<'inherit' | string>('inherit')
  const [diarizationModel, setDiarizationModelLocal] = useState<'inherit' | 'off' | string>('inherit')
  const [transcribeOk, setTranscribeOk] = useState(false)
  const [summarizeModel, setSummarizeModelLocal] = useState<'inherit' | string>('inherit')
  const [summarizeOk, setSummarizeOk] = useState(false)
  const [captureBotName, setCaptureBotNameLocal] = useState('')
  const [captureBotOk, setCaptureBotOk] = useState(false)
  const [defaultRoute, setDefaultRouteLocal] = useState<DefaultRoute>(() => {
    const stored = normalizeDefaultRoute(me?.user.default_route)
    const allowed = allowedDefaultRoutes(me)
    return stored && allowed.includes(stored) ? stored : allowed[0]
  })

  const hasOrg = Boolean(me?.org)
  const showLocalAuth = localAuthProfileVisible(me)
  const apiAllowed = !me?.org || Boolean(me.org.tariff.api_enabled)
  const activeTokens = tokens.filter((tok) => !tok.revoked)
  const [backupTranscripts, setBackupTranscripts] = useState(true)
  const [backupSummaries, setBackupSummaries] = useState(true)
  const [backupSkills, setBackupSkills] = useState(true)
  const [backupFormat, setBackupFormat] = useState<'zip' | 'tgz'>('zip')
  const [backingUp, setBackingUp] = useState(false)
  const [disablePw, setDisablePw] = useState('')
  const [disableCode, setDisableCode] = useState('')
  const [mfaBusy, setMfaBusy] = useState(false)
  const [tokenTotp, setTokenTotp] = useState('')
  const [tokenTotpOpen, setTokenTotpOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deletePreview, setDeletePreview] = useState<AccountDeletePreview | null>(null)
  const [deletePassword, setDeletePassword] = useState('')
  const [deleteTotp, setDeleteTotp] = useState('')
  const [deleteSuccessor, setDeleteSuccessor] = useState('')
  const [deleteBusy, setDeleteBusy] = useState(false)

  const canDeleteAccount = Boolean(me && !me.user.is_instance_admin)
  const showLocalAuthDelete = localAuthProfileVisible(me)

  const orgLabel = useMemo(() => {
    if (!me?.org) return t('profile.noOrg')
    if (me.org.is_personal) return t('profile.personalOrg')
    return me.org.name
  }, [me, t])

  const mfaSummary = useMemo(() => {
    if (!showLocalAuth) return { label: t('profile.mfaViaSso'), tone: 'default' as const }
    if (me?.mfa_enabled) return { label: t('profile.mfaOn'), tone: 'proxy-up' as const }
    return { label: t('profile.mfaOff'), tone: 'proxy-down' as const }
  }, [me, showLocalAuth, t])

  async function load() {
    const r = await api<{ items: ApiToken[] }>('/auth/tokens')
    setTokens(r.items)
  }

  useEffect(() => {
    load().catch(showError)
  }, [])

  useEffect(() => {
    const stored = normalizeDefaultRoute(me?.user.default_route)
    const allowed = allowedDefaultRoutes(me)
    if (stored && allowed.includes(stored)) setDefaultRouteLocal(stored)
    else if (allowed.length > 0) setDefaultRouteLocal(allowed[0])
    setShowOnlyMyItemsLocal(Boolean(me?.user.show_only_my_items))
  }, [me])

  useEffect(() => {
    if (!me) return
    setDateTimeFormatLocal(
      me.user.date_time_format && DATE_TIME_FORMATS.includes(me.user.date_time_format as DateTimeFormatId)
        ? (me.user.date_time_format as DateTimeFormatId)
        : 'inherit',
    )
    setTimezoneLocal(me.user.timezone || 'inherit')
    setAsrModelLocal(me.user.asr_model || 'inherit')
    if (me.user.diarization_model == null) setDiarizationModelLocal('inherit')
    else if (me.user.diarization_model === '') setDiarizationModelLocal('off')
    else setDiarizationModelLocal(me.user.diarization_model)
    setSummarizeModelLocal(me.user.summarize_model || 'inherit')
    setCaptureBotNameLocal(me.user.capture_bot_display_name || '')
  }, [me])

  const dateTimePreview = useMemo(() => {
    if (!me) return ''
    const prefs: DateTimePrefs = {
      ...me.date_time_prefs,
      format: dateTimeFormat === 'inherit' ? me.date_time_prefs.instance_format : dateTimeFormat,
      timezone: timezone === 'inherit' ? me.date_time_prefs.instance_timezone : timezone,
    }
    return formatDateTime(new Date().toISOString(), prefs, i18n.language)
  }, [me, dateTimeFormat, timezone, i18n.language])

  const availableDiarizationModels = useMemo(() => {
    if (!me) return []
    const asr = resolveEffectiveAsr(asrModel, me.transcribe_prefs)
    return diarizationOptionsForAsr(me.transcribe_models, asr)
  }, [me, asrModel])

  const transcribeComboValid = useMemo(() => {
    if (!me) return true
    const asr = resolveEffectiveAsr(asrModel, me.transcribe_prefs)
    const diar = resolveEffectiveDiarization(diarizationModel, me.transcribe_prefs)
    return isDispatchableCombo(me.transcribe_models, asr, diar)
  }, [me, asrModel, diarizationModel])

  const summarizeModelValid = useMemo(() => {
    if (!me) return true
    const model = resolveEffectiveSummarizeModel(summarizeModel, me.summarize_prefs)
    return isAvailableSummarizeModel(me.summarize_models, model)
  }, [me, summarizeModel])

  async function saveDefaultRoute() {
    setRouteOk(false)
    setScopeOk(false)
    setOk(false)
    try {
      await setDefaultRoute(defaultRoute)
      setRouteOk(true)
    } catch (e) {
      showError(e)
    }
  }

  async function saveShowOnlyMyItems() {
    setScopeOk(false)
    setRouteOk(false)
    setOk(false)
    try {
      await setShowOnlyMyItems(showOnlyMyItems)
      setScopeOk(true)
    } catch (e) {
      showError(e)
    }
  }

  async function saveDateTimePrefs() {
    setDateTimeOk(false)
    setRouteOk(false)
    setOk(false)
    setTranscribeOk(false)
    try {
      await setDateTimeFormat(dateTimeFormat === 'inherit' ? null : dateTimeFormat)
      await setTimezone(timezone === 'inherit' ? null : timezone)
      setDateTimeOk(true)
    } catch (e) {
      showError(e)
    }
  }

  async function saveTranscribePrefs() {
    setTranscribeOk(false)
    setSummarizeOk(false)
    setRouteOk(false)
    setOk(false)
    setDateTimeOk(false)
    try {
      await api('/me', {
        method: 'PATCH',
        body: JSON.stringify({
          asr_model: asrModel === 'inherit' ? null : asrModel,
          diarization_model: diarizationModel === 'inherit' ? null : diarizationModel === 'off' ? '' : diarizationModel,
        }),
      })
      await refresh()
      setTranscribeOk(true)
    } catch (e) {
      showError(e)
    }
  }

  async function saveSummarizePrefs() {
    setSummarizeOk(false)
    setTranscribeOk(false)
    setRouteOk(false)
    setOk(false)
    setDateTimeOk(false)
    try {
      await api('/me', {
        method: 'PATCH',
        body: JSON.stringify({
          summarize_model: summarizeModel === 'inherit' ? null : summarizeModel,
        }),
      })
      await refresh()
      setSummarizeOk(true)
    } catch (e) {
      showError(e)
    }
  }

  async function saveCaptureBotPrefs() {
    setCaptureBotOk(false)
    setSummarizeOk(false)
    setTranscribeOk(false)
    setRouteOk(false)
    setOk(false)
    setDateTimeOk(false)
    try {
      const trimmed = captureBotName.trim()
      await api('/me', {
        method: 'PATCH',
        body: JSON.stringify({
          capture_bot_display_name: trimmed ? trimmed : null,
        }),
      })
      await refresh()
      setCaptureBotOk(true)
    } catch (e) {
      showError(e)
    }
  }

  const captureBotEffective = useMemo(() => {
    if (!me) return ''
    const custom = captureBotName.trim()
    if (custom) return custom
    return me.capture_prefs.org_bot_display_name
  }, [me, captureBotName])

  async function changePw(e: FormEvent) {
    e.preventDefault()
    setOk(false)
    setRouteOk(false)
    try {
      await api('/auth/password/change', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: next }),
      })
      setCurrent('')
      setNext('')
      setOk(true)
      await refresh()
    } catch (e) {
      showError(e)
    }
  }

  async function createToken(totpCode?: string) {
    const name = tokenName.trim()
    if (!name || !apiAllowed) return
    if (me?.mfa_enabled && !totpCode) {
      setTokenTotpOpen(true)
      return
    }
    setCopied(false)
    setCreating(true)
    try {
      const body: { name: string; totp_code?: string } = { name }
      if (me?.mfa_enabled && totpCode) body.totp_code = totpCode
      const row = await api<ApiToken>('/auth/tokens', { method: 'POST', body: JSON.stringify(body) })
      setSecret(row.token || null)
      setTokenName('')
      setTokenTotp('')
      setTokenTotpOpen(false)
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setCreating(false)
    }
  }

  async function disableMfa(e: FormEvent) {
    e.preventDefault()
    setMfaBusy(true)
    try {
      await api('/auth/mfa/disable', {
        method: 'POST',
        body: JSON.stringify({ password: disablePw, code: disableCode.trim() }),
      })
      setDisablePw('')
      setDisableCode('')
      await logout()
    } catch (err) {
      showError(err)
    } finally {
      setMfaBusy(false)
    }
  }

  async function copySecret() {
    if (!secret) return
    try {
      await navigator.clipboard.writeText(secret)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard unavailable */
    }
  }

  async function revoke(id: string) {
    try {
      await api(`/auth/tokens/${id}`, { method: 'DELETE' })
      await load()
    } catch (e) {
      showError(e)
    }
  }

  async function openDeleteAccount() {
    setDeletePassword('')
    setDeleteTotp('')
    setDeleteSuccessor('')
    setDeleteOpen(true)
    try {
      const preview = await api<AccountDeletePreview>('/me/account-delete')
      setDeletePreview(preview)
      if (preview.candidates.length === 1) setDeleteSuccessor(preview.candidates[0].id)
    } catch (e) {
      setDeleteOpen(false)
      showError(e)
    }
  }

  async function confirmDeleteAccount() {
    setDeleteBusy(true)
    try {
      const body: {
        password?: string
        totp_code?: string
        successor_user_id?: string
      } = {}
      if (showLocalAuthDelete && deletePassword) body.password = deletePassword
      if (me?.mfa_enabled && deleteTotp.trim()) body.totp_code = deleteTotp.trim()
      if (deletePreview?.requires_successor) body.successor_user_id = deleteSuccessor
      await api('/me/account-delete', { method: 'POST', body: JSON.stringify(body) })
      setDeleteOpen(false)
      await logout()
      nav('/login', { replace: true })
    } catch (e) {
      showError(e)
    } finally {
      setDeleteBusy(false)
    }
  }

  async function downloadBackup() {
    if (!backupTranscripts && !backupSummaries && !backupSkills) {
      showError(new Error(t('profile.backupNothingSelected')))
      return
    }
    setBackingUp(true)
    try {
      const params = new URLSearchParams()
      if (backupTranscripts) params.set('transcripts', 'true')
      if (backupSummaries) params.set('summaries', 'true')
      if (backupSkills) params.set('skills', 'true')
      params.set('format', backupFormat)
      const ext = backupFormat === 'zip' ? 'zip' : 'tar.gz'
      const stamp = new Date().toISOString().slice(0, 10)
      await apiDownload(`/me/backup?${params}`, `idigest-backup-${stamp}.${ext}`)
    } catch (e) {
      showError(e)
    } finally {
      setBackingUp(false)
    }
  }

  const roleBadge = me?.user.is_instance_admin
    ? t('profile.roleInstanceAdmin')
    : me?.user.role === 'org_admin'
      ? t('profile.roleOrgAdmin')
      : me?.user.role === 'org_member'
        ? t('profile.roleOrgMember')
        : null

  return (
    <AdminPage>
      {me && (
        <div className="card profile-identity">
          <div className="profile-identity-main">
            <span className="stat-label">{t('common.email')}</span>
            <span className="profile-identity-email" title={me.user.email}>{me.user.email}</span>
          </div>
          {roleBadge && <span className="badge profile-identity-badge">{roleBadge}</span>}
        </div>
      )}

      <StatGrid>
        <StatCard label={t('profile.kpiOrg')} value={orgLabel} tone="ops" />
        <StatCard label={t('profile.kpiMfa')} value={mfaSummary.label} tone={mfaSummary.tone} />
        <StatCard
          label={t('profile.kpiTokens')}
          value={formatInteger(activeTokens.length)}
          tone="summarize"
        />
        <StatCard
          label={t('profile.kpiApi')}
          value={apiAllowed ? t('profile.apiOn') : t('profile.apiOff')}
          tone={apiAllowed ? 'proxy-up' : 'proxy-na'}
        />
      </StatGrid>

      <div className="profile-settings-grid">
        <AdminFormCard title={t('profile.defaultRoute')} lead={t('profile.defaultRouteHint')}>
          <label>
            {t('profile.defaultRoute')}
            <select
              value={defaultRoute}
              onChange={(e) => {
                setRouteOk(false)
                setDefaultRouteLocal(e.target.value as DefaultRoute)
              }}
            >
              {allowedDefaultRoutes(me).map((route) => (
                <option key={route} value={route}>
                  {defaultRouteLabel(route, t)}
                </option>
              ))}
            </select>
          </label>
          <div className="profile-actions">
            <button className="primary" type="button" onClick={() => void saveDefaultRoute()}>
              {t('common.save')}
            </button>
            {routeOk && <p className="ok">{t('profile.saved')}</p>}
          </div>
        </AdminFormCard>

        {isOrgAdmin(me) && (
          <AdminFormCard title={t('profile.showOnlyMyItems')} lead={t('profile.showOnlyMyItemsHint')}>
            <label className="profile-check-row">
              <input
                type="checkbox"
                checked={showOnlyMyItems}
                onChange={(e) => {
                  setScopeOk(false)
                  setShowOnlyMyItemsLocal(e.target.checked)
                }}
              />
              {t('profile.showOnlyMyItemsLabel')}
            </label>
            <div className="profile-actions">
              <button className="primary" type="button" onClick={() => void saveShowOnlyMyItems()}>
                {t('common.save')}
              </button>
              {scopeOk && <p className="ok">{t('profile.saved')}</p>}
            </div>
          </AdminFormCard>
        )}

        {me && (me.transcribe_models.asr_models.length > 0 || me.transcribe_models.diarization_models.length > 0) && (
          <AdminFormCard title={t('profile.transcribeTitle')} lead={t('profile.transcribeHint')}>
            <label>
              {t('instance.asr')}
              <select
                value={asrModel}
                onChange={(e) => {
                  setTranscribeOk(false)
                  const nextAsr = e.target.value
                  setAsrModelLocal(nextAsr)
                  if (!me) return
                  const effectiveAsr = resolveEffectiveAsr(nextAsr, me.transcribe_prefs)
                  const allowedDiar = diarizationOptionsForAsr(me.transcribe_models, effectiveAsr)
                  if (diarizationModel !== 'inherit' && diarizationModel !== 'off' && !allowedDiar.includes(diarizationModel)) {
                    setDiarizationModelLocal('inherit')
                  }
                }}
              >
                <option value="inherit">
                  {t('profile.dateTimeInherit', { value: me.transcribe_prefs.instance_asr_model })}
                </option>
                {me.transcribe_models.asr_models.map((modelId) => (
                  <option key={modelId} value={modelId}>{modelId}</option>
                ))}
              </select>
            </label>
            <label>
              {t('instance.diarization')}
              <select
                value={diarizationModel}
                onChange={(e) => {
                  setTranscribeOk(false)
                  setDiarizationModelLocal(e.target.value)
                }}
              >
                <option value="inherit">
                  {t('profile.transcribeDiarizationInherit', {
                    value: me.transcribe_prefs.instance_diarization_model || t('instance.diarizationOff'),
                  })}
                </option>
                <option value="off">{t('instance.diarizationOff')}</option>
                {availableDiarizationModels.map((modelId) => (
                  <option key={modelId} value={modelId}>{modelId}</option>
                ))}
              </select>
            </label>
            <p className="muted">
              {t('profile.transcribePreview', {
                asr: resolveEffectiveAsr(asrModel, me.transcribe_prefs),
                diarization: resolveEffectiveDiarization(diarizationModel, me.transcribe_prefs) || t('instance.diarizationOff'),
              })}
            </p>
            {!transcribeComboValid ? (
              <p className="err">{t('profile.transcribeComboInvalid')}</p>
            ) : null}
            <div className="profile-actions">
              <button className="primary" type="button" disabled={!transcribeComboValid} onClick={() => void saveTranscribePrefs()}>
                {t('common.save')}
              </button>
              {transcribeOk && <p className="ok">{t('profile.saved')}</p>}
            </div>
          </AdminFormCard>
        )}

        {me && me.summarize_models.summarize_models.length > 0 && (
          <AdminFormCard title={t('profile.summarizeTitle')} lead={t('profile.summarizeHint')}>
            <label>
              {t('instance.summarizeModelLabel')}
              <select
                value={summarizeModel}
                onChange={(e) => {
                  setSummarizeOk(false)
                  setSummarizeModelLocal(e.target.value)
                }}
              >
                <option value="inherit">
                  {t('profile.dateTimeInherit', {
                    value: me.summarize_prefs.instance_summarize_model || t('instance.summarizeModelUnset'),
                  })}
                </option>
                {me.summarize_models.summarize_models.map((modelId) => (
                  <option key={modelId} value={modelId}>{modelId}</option>
                ))}
              </select>
            </label>
            <p className="muted">
              {t('profile.summarizePreview', {
                model: resolveEffectiveSummarizeModel(summarizeModel, me.summarize_prefs) || t('instance.summarizeModelUnset'),
              })}
            </p>
            {!summarizeModelValid ? (
              <p className="err">{t('profile.summarizeModelInvalid')}</p>
            ) : null}
            <div className="profile-actions">
              <button className="primary" type="button" disabled={!summarizeModelValid} onClick={() => void saveSummarizePrefs()}>
                {t('common.save')}
              </button>
              {summarizeOk && <p className="ok">{t('profile.saved')}</p>}
            </div>
          </AdminFormCard>
        )}

        {me?.capture_prefs.capture_enabled ? (
          <AdminFormCard title={t('profile.captureBotTitle')} lead={t('profile.captureBotHint')}>
            <label>
              {t('org.captureBotDisplayName')}
              <input
                type="text"
                value={captureBotName}
                maxLength={128}
                placeholder={t('profile.captureBotInherit', { value: me.capture_prefs.org_bot_display_name })}
                onChange={(e) => {
                  setCaptureBotOk(false)
                  setCaptureBotNameLocal(e.target.value)
                }}
              />
            </label>
            <p className="muted">{t('org.captureBotDisplayNameHint')}</p>
            <p className="muted">{t('profile.captureBotPreview', { name: captureBotEffective })}</p>
            <div className="profile-actions">
              <button className="primary" type="button" onClick={() => void saveCaptureBotPrefs()}>
                {t('common.save')}
              </button>
              {captureBotOk && <p className="ok">{t('profile.saved')}</p>}
            </div>
          </AdminFormCard>
        ) : null}

        <AdminFormCard title={t('profile.dateTimeTitle')} lead={t('profile.dateTimeHint')}>
          <label>
            {t('profile.dateTimeFormat')}
            <select
              value={dateTimeFormat}
              onChange={(e) => {
                setDateTimeOk(false)
                setDateTimeFormatLocal(e.target.value as 'inherit' | DateTimeFormatId)
              }}
            >
              <option value="inherit">
                {t('profile.dateTimeInherit', {
                  value: t(`dateTime.format.${me?.date_time_prefs.instance_format ?? 'eu_24h'}`),
                })}
              </option>
              {DATE_TIME_FORMATS.map((id) => (
                <option key={id} value={id}>
                  {t(`dateTime.format.${id}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t('profile.timezone')}
            <select
              value={timezone}
              onChange={(e) => {
                setDateTimeOk(false)
                setTimezoneLocal(e.target.value)
              }}
            >
              <option value="inherit">
                {t('profile.dateTimeInherit', {
                  value: me?.date_time_prefs.instance_timezone ?? 'GMT+0',
                })}
              </option>
              {TIMEZONE_OPTIONS.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
              {timezone !== 'inherit' && !TIMEZONE_OPTIONS.includes(timezone as (typeof TIMEZONE_OPTIONS)[number]) && (
                <option value={timezone}>{timezone}</option>
              )}
            </select>
          </label>
          <p className="muted">
            {t('profile.dateTimePreview', { sample: dateTimePreview })}
          </p>
          <div className="profile-actions">
            <button className="primary" type="button" onClick={() => void saveDateTimePrefs()}>
              {t('common.save')}
            </button>
            {dateTimeOk && <p className="ok">{t('profile.saved')}</p>}
          </div>
        </AdminFormCard>

        {showLocalAuth && me && (
          <AdminFormCard title={t('mfa.title')} lead={t('mfa.profileLead')}>
            {me.mfa_enabled ? (
              <form className="stack" onSubmit={(e) => void disableMfa(e)}>
                <p className="ok">{t('mfa.enabled')}</p>
                {me.mfa_required && <p className="muted">{t('mfa.requiredByOrg')}</p>}
                {!me.mfa_required && (
                  <>
                    <label>
                      {t('common.password')}
                      <input
                        type="password"
                        required
                        value={disablePw}
                        onChange={(e) => setDisablePw(e.target.value)}
                        autoComplete="current-password"
                      />
                    </label>
                    <label>
                      {t('mfa.codeOrRecovery')}
                      <input
                        type="text"
                        required
                        value={disableCode}
                        onChange={(e) => setDisableCode(e.target.value)}
                      />
                    </label>
                    <button className="danger" disabled={mfaBusy} type="submit">
                      {t('mfa.disable')}
                    </button>
                  </>
                )}
              </form>
            ) : (
              <MfaSetupPanel onComplete={() => void refresh()} />
            )}
          </AdminFormCard>
        )}

        {showLocalAuth && (
          <AdminFormCard title={t('auth.changePassword')}>
            <form className="stack" onSubmit={(e) => void changePw(e)}>
              <label>
                {t('auth.currentPassword')}
                <input type="password" required value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
              </label>
              <label>
                {t('auth.newPassword')}
                <input type="password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
              </label>
              <div className="profile-actions">
                <button className="primary" type="submit">{t('common.save')}</button>
                {ok && <p className="ok">{t('profile.saved')}</p>}
              </div>
            </form>
          </AdminFormCard>
        )}
      </div>

      {hasOrg && (
        <AdminFormCard title={t('profile.backup')} lead={t('profile.backupLead')}>
          <div className="profile-backup-body">
            <div className="profile-backup-group">
              <span className="profile-backup-label">{t('profile.backupInclude')}</span>
              <div className="profile-backup-checks">
                <label className="profile-check-row">
                  <input
                    type="checkbox"
                    checked={backupTranscripts}
                    onChange={(e) => setBackupTranscripts(e.target.checked)}
                  />
                  {t('library.transcripts')}
                </label>
                <label className="profile-check-row">
                  <input
                    type="checkbox"
                    checked={backupSummaries}
                    onChange={(e) => setBackupSummaries(e.target.checked)}
                  />
                  {t('library.summaries')}
                </label>
                <label className="profile-check-row">
                  <input
                    type="checkbox"
                    checked={backupSkills}
                    onChange={(e) => setBackupSkills(e.target.checked)}
                  />
                  {t('nav.skills')}
                </label>
              </div>
            </div>
            <div className="profile-backup-group">
              <span className="profile-backup-label">{t('profile.backupFormat')}</span>
              <Segmented
                variant="outline"
                ariaLabel={t('profile.backupFormat')}
                value={backupFormat}
                onChange={setBackupFormat}
                options={[
                  { value: 'zip', label: 'ZIP' },
                  { value: 'tgz', label: 'TGZ' },
                ]}
              />
            </div>
          </div>
          <div className="profile-actions profile-backup-actions">
            <button
              className="primary"
              type="button"
              disabled={backingUp || (!backupTranscripts && !backupSummaries && !backupSkills)}
              onClick={() => void downloadBackup()}
            >
              {backingUp ? t('common.loading') : t('profile.downloadBackup')}
            </button>
          </div>
        </AdminFormCard>
      )}

      <AdminTableCard title={t('profile.tokens')} lead={t('profile.tokensLead')}>
        {!apiAllowed && (
          <div className="profile-alert" role="status">
            {t('profile.apiDisabled')}
          </div>
        )}

        {secret && (
          <div className="profile-secret-card">
            <p className="profile-secret-title">{t('profile.secretOnce')}</p>
            <div className="profile-secret-row">
              <code className="secret profile-secret-value">{secret}</code>
              <button type="button" onClick={() => void copySecret()}>
                {copied ? t('profile.copied') : t('profile.copy')}
              </button>
            </div>
          </div>
        )}

        {tokenTotpOpen && (
          <div className="profile-secret-card stack">
            <p className="profile-secret-title">{t('mfa.tokenStepUp')}</p>
            <label>
              {t('mfa.code')}
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={tokenTotp}
                onChange={(e) => setTokenTotp(e.target.value)}
              />
            </label>
            <div className="row">
              <button
                className="primary"
                type="button"
                disabled={creating || !tokenTotp.trim()}
                onClick={() => void createToken(tokenTotp.trim())}
              >
                {creating ? t('common.loading') : t('profile.newToken')}
              </button>
              <button type="button" onClick={() => { setTokenTotpOpen(false); setTokenTotp('') }}>
                {t('common.cancel')}
              </button>
            </div>
          </div>
        )}

        <div className="profile-token-create">
          <label className="grow">
            {t('profile.tokenName')}
            <input
              placeholder={t('profile.tokenNamePlaceholder')}
              value={tokenName}
              onChange={(e) => setTokenName(e.target.value)}
              disabled={!apiAllowed || creating}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  void createToken()
                }
              }}
            />
          </label>
          <button
            className="primary profile-create-btn"
            type="button"
            disabled={!apiAllowed || creating || !tokenName.trim()}
            onClick={() => void createToken()}
          >
            {creating ? t('common.loading') : t('profile.newToken')}
          </button>
        </div>

        {tokens.length === 0 ? (
          <p className="stats-empty">{t('profile.noTokens')}</p>
        ) : (
          <ul className="profile-token-list">
            {tokens.map((tok) => (
              <li key={tok.id} className={`profile-token-item${tok.revoked ? ' is-revoked' : ''}`}>
                <div className="profile-token-main">
                  <div className="profile-token-name">{tok.name}</div>
                  <div className="profile-token-meta">
                    <span className="profile-token-prefix">{tok.prefix}</span>
                    <span className="profile-token-date">{fmtDate(tok.created_at)}</span>
                  </div>
                  <div className="profile-token-badges">
                    {tok.revoked && <span className="badge">{t('profile.revoked')}</span>}
                    {tok.blocked_by_tariff && <span className="badge warn">{t('profile.blockedTariff')}</span>}
                  </div>
                </div>
                {!tok.revoked && (
                  <button type="button" className="danger" onClick={() => void revoke(tok.id)}>
                    {t('profile.revoke')}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {activeTokens.length > 0 && (
          <p className="muted profile-token-count">
            {t('profile.tokenCount', { count: activeTokens.length })}
          </p>
        )}
      </AdminTableCard>

      {canDeleteAccount && (
        <AdminFormCard title={t('profile.deleteAccount')} lead={t('profile.deleteAccountLead')}>
          <button type="button" className="danger" onClick={() => void openDeleteAccount()}>
            {t('profile.deleteAccount')}
          </button>
        </AdminFormCard>
      )}

      {deleteOpen && deletePreview && (
        <Modal
          onClose={() => {
            if (deleteBusy) return
            setDeleteOpen(false)
          }}
          closeOnBackdrop={!deleteBusy}
          panelClassName="stack"
        >
          <h2>{t('profile.deleteAccount')}</h2>
          <p className="err">{t('profile.deleteAccountLead')}</p>
          {deletePreview.will_delete_org && (
            <p className="err">{t('profile.deleteAccountWillDeleteOrg')}</p>
          )}
          {deletePreview.requires_successor && (
            <>
              <p className="muted">{t('profile.deleteAccountSuccessorHint')}</p>
              <label>
                {t('profile.deleteAccountSuccessor')}
                <select
                  required
                  value={deleteSuccessor}
                  disabled={deleteBusy}
                  onChange={(e) => setDeleteSuccessor(e.target.value)}
                >
                  {deletePreview.candidates.length > 1 && (
                    <option value="">{t('org.target')}</option>
                  )}
                  {deletePreview.candidates.map((c) => (
                    <option key={c.id} value={c.id}>{c.email}</option>
                  ))}
                </select>
              </label>
            </>
          )}
          {showLocalAuthDelete && (
            <label>
              {t('profile.deleteAccountPassword')}
              <input
                type="password"
                required
                autoComplete="current-password"
                value={deletePassword}
                disabled={deleteBusy}
                onChange={(e) => setDeletePassword(e.target.value)}
              />
            </label>
          )}
          {me?.mfa_enabled && (
            <label>
              {t('profile.deleteAccountTotp')}
              <input
                type="text"
                required
                autoComplete="one-time-code"
                value={deleteTotp}
                disabled={deleteBusy}
                onChange={(e) => setDeleteTotp(e.target.value)}
              />
            </label>
          )}
          <div className="row modal-actions">
            <button
              type="button"
              className="danger"
              disabled={
                deleteBusy
                || (deletePreview.requires_successor && !deleteSuccessor)
                || (showLocalAuthDelete && !deletePassword)
                || (Boolean(me?.mfa_enabled) && !deleteTotp.trim())
              }
              onClick={() => void confirmDeleteAccount()}
            >
              {deleteBusy ? t('profile.deleteAccountBusy') : t('profile.deleteAccountConfirm')}
            </button>
            <button type="button" disabled={deleteBusy} onClick={() => setDeleteOpen(false)}>
              {t('common.cancel')}
            </button>
          </div>
        </Modal>
      )}

    </AdminPage>
  )
}
