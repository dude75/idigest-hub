import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { api, apiDownload, apiUpload } from '../api'
import { useAuth } from '../auth'
import { AdminFormCard, AdminPage, AdminTableCard } from '../components/AdminSection'
import { Modal } from '../components/Modal'
import { MfaSetupPanel } from '../components/MfaSetupPanel'
import { StatCard, StatGrid } from '../components/StatCard'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { AdminFormActions, AppSubmitButton, HubBadge, type HubBadgeTone } from '../components/app/AdminUi'
import { AppCheckboxRow, AppInputField, AppSelectField } from '../components/app/AppFormControls'
import { AppUrlCopyRow } from '../components/app/AppUrlCopyRow'
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
  const { me, refresh, setDefaultRoute, setDateTimeFormat, setTimezone, logout } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [tokens, setTokens] = useState<ApiToken[]>([])
  const [tokenName, setTokenName] = useState('')
  const [secret, setSecret] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [ok, setOk] = useState(false)
  const [routeOk, setRouteOk] = useState(false)
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
  const [restoringUp, setRestoringUp] = useState(false)
  const [restoreMessage, setRestoreMessage] = useState<string | null>(null)
  const restoreInputRef = useRef<HTMLInputElement>(null)
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

  const storedDefaultRoute = useMemo((): DefaultRoute => {
    const stored = normalizeDefaultRoute(me?.user.default_route)
    const allowed = allowedDefaultRoutes(me)
    return stored && allowed.includes(stored) ? stored : allowed[0]
  }, [me])

  const defaultRouteDirty = defaultRoute !== storedDefaultRoute

  const savedDateTimeFormat = useMemo((): 'inherit' | DateTimeFormatId => {
    if (!me?.user.date_time_format) return 'inherit'
    return DATE_TIME_FORMATS.includes(me.user.date_time_format as DateTimeFormatId)
      ? (me.user.date_time_format as DateTimeFormatId)
      : 'inherit'
  }, [me])

  const savedTimezone = me?.user.timezone || 'inherit'
  const dateTimeDirty = dateTimeFormat !== savedDateTimeFormat || timezone !== savedTimezone

  const savedAsrModel = me?.user.asr_model || 'inherit'
  const savedDiarizationModel =
    me?.user.diarization_model == null
      ? 'inherit'
      : me.user.diarization_model === ''
        ? 'off'
        : me.user.diarization_model
  const transcribeDirty = asrModel !== savedAsrModel || diarizationModel !== savedDiarizationModel
  const transcribeReady = transcribeDirty && transcribeComboValid

  const savedSummarizeModel = me?.user.summarize_model || 'inherit'
  const summarizeDirty = summarizeModel !== savedSummarizeModel
  const summarizeReady = summarizeDirty && summarizeModelValid

  const savedCaptureBotName = me?.user.capture_bot_display_name ?? ''
  const captureBotDirty = captureBotName.trim() !== savedCaptureBotName.trim()

  const passwordReady = current.trim().length > 0 && next.trim().length >= 8

  async function saveDefaultRoute() {
    setRouteOk(false)
    setOk(false)
    try {
      await setDefaultRoute(defaultRoute)
      setRouteOk(true)
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

  async function restoreBackup(file: File) {
    const lower = file.name.toLowerCase()
    if (!lower.endsWith('.zip') && !lower.endsWith('.tar.gz') && !lower.endsWith('.tgz')) {
      showError(new Error(t('profile.restoreBackupInvalidFile')))
      return
    }
    setRestoreMessage(null)
    setRestoringUp(true)
    try {
      const body = new FormData()
      body.append('file', file)
      const result = await apiUpload<{
        mode: string
        transcripts: { created: number; updated: number }
        summaries: { created: number; updated: number }
        skills: { created: number; updated: number }
      }>('/me/backup/restore', body)
      setRestoreMessage(
        t('profile.restoreBackupDone', {
          mode: result.mode,
          tCreated: result.transcripts.created,
          tUpdated: result.transcripts.updated,
          sCreated: result.summaries.created,
          sUpdated: result.summaries.updated,
          kCreated: result.skills.created,
          kUpdated: result.skills.updated,
        }),
      )
    } catch (e) {
      showError(e)
    } finally {
      setRestoringUp(false)
      if (restoreInputRef.current) restoreInputRef.current.value = ''
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

  const roleBadgeTone: HubBadgeTone = me?.user.is_instance_admin
    ? 'primary'
    : me?.user.role === 'org_admin'
      ? 'primary'
      : 'muted'

  return (
    <AdminPage>
      {me && (
        <Card className="profile-identity">
          <CardHeader className="space-y-2">
            <CardDescription className="stat-label m-0">{t('common.email')}</CardDescription>
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <CardTitle className="min-w-0 break-all text-lg font-semibold leading-snug" title={me.user.email}>
                {me.user.email}
              </CardTitle>
              {roleBadge ? <HubBadge tone={roleBadgeTone}>{roleBadge}</HubBadge> : null}
            </div>
          </CardHeader>
        </Card>
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
          <AppSelectField
            label={t('profile.defaultRoute')}
            htmlFor="profile-default-route"
            value={defaultRoute}
            onValueChange={(route) => {
              setRouteOk(false)
              setDefaultRouteLocal(route as DefaultRoute)
            }}
            options={allowedDefaultRoutes(me).map((route) => ({
              value: route,
              label: defaultRouteLabel(route, t),
            }))}
          />
          <AdminFormActions className="profile-actions">
            <AppSubmitButton ready={defaultRouteDirty} onClick={() => void saveDefaultRoute()}>
              {t('common.save')}
            </AppSubmitButton>
            {routeOk ? <p className="ok">{t('profile.saved')}</p> : null}
          </AdminFormActions>
        </AdminFormCard>

        {me && (me.transcribe_models.asr_models.length > 0 || me.transcribe_models.diarization_models.length > 0) && (
          <AdminFormCard title={t('profile.transcribeTitle')} lead={t('profile.transcribeHint')}>
            <AppSelectField
              label={t('instance.asr')}
              htmlFor="profile-asr"
              value={asrModel}
              onValueChange={(nextAsr) => {
                setTranscribeOk(false)
                setAsrModelLocal(nextAsr)
                if (!me) return
                const effectiveAsr = resolveEffectiveAsr(nextAsr, me.transcribe_prefs)
                const allowedDiar = diarizationOptionsForAsr(me.transcribe_models, effectiveAsr)
                if (diarizationModel !== 'inherit' && diarizationModel !== 'off' && !allowedDiar.includes(diarizationModel)) {
                  setDiarizationModelLocal('inherit')
                }
              }}
              options={[
                {
                  value: 'inherit',
                  label: t('profile.dateTimeInherit', { value: me.transcribe_prefs.instance_asr_model }),
                },
                ...me.transcribe_models.asr_models.map((modelId) => ({ value: modelId, label: modelId })),
              ]}
            />
            <AppSelectField
              label={t('instance.diarization')}
              htmlFor="profile-diarization"
              value={diarizationModel}
              onValueChange={(next) => {
                setTranscribeOk(false)
                setDiarizationModelLocal(next)
              }}
              options={[
                {
                  value: 'inherit',
                  label: t('profile.transcribeDiarizationInherit', {
                    value: me.transcribe_prefs.instance_diarization_model || t('instance.diarizationOff'),
                  }),
                },
                { value: 'off', label: t('instance.diarizationOff') },
                ...availableDiarizationModels.map((modelId) => ({ value: modelId, label: modelId })),
              ]}
            />
            <p className="muted">
              {t('profile.transcribePreview', {
                asr: resolveEffectiveAsr(asrModel, me.transcribe_prefs),
                diarization: resolveEffectiveDiarization(diarizationModel, me.transcribe_prefs) || t('instance.diarizationOff'),
              })}
            </p>
            {!transcribeComboValid ? (
              <p className="err">{t('profile.transcribeComboInvalid')}</p>
            ) : null}
            <AdminFormActions className="profile-actions">
              <AppSubmitButton ready={transcribeReady} onClick={() => void saveTranscribePrefs()}>
                {t('common.save')}
              </AppSubmitButton>
              {transcribeOk ? <p className="ok">{t('profile.saved')}</p> : null}
            </AdminFormActions>
          </AdminFormCard>
        )}

        {me && me.summarize_models.summarize_models.length > 0 && (
          <AdminFormCard title={t('profile.summarizeTitle')} lead={t('profile.summarizeHint')}>
            <AppSelectField
              label={t('instance.summarizeModelLabel')}
              htmlFor="profile-summarize"
              value={summarizeModel}
              onValueChange={(next) => {
                setSummarizeOk(false)
                setSummarizeModelLocal(next)
              }}
              options={[
                {
                  value: 'inherit',
                  label: t('profile.dateTimeInherit', {
                    value: me.summarize_prefs.instance_summarize_model || t('instance.summarizeModelUnset'),
                  }),
                },
                ...me.summarize_models.summarize_models.map((modelId) => ({ value: modelId, label: modelId })),
              ]}
            />
            <p className="muted">
              {t('profile.summarizePreview', {
                model: resolveEffectiveSummarizeModel(summarizeModel, me.summarize_prefs) || t('instance.summarizeModelUnset'),
              })}
            </p>
            {!summarizeModelValid ? (
              <p className="err">{t('profile.summarizeModelInvalid')}</p>
            ) : null}
            <AdminFormActions className="profile-actions">
              <AppSubmitButton ready={summarizeReady} onClick={() => void saveSummarizePrefs()}>
                {t('common.save')}
              </AppSubmitButton>
              {summarizeOk ? <p className="ok">{t('profile.saved')}</p> : null}
            </AdminFormActions>
          </AdminFormCard>
        )}

        {me?.capture_prefs.capture_enabled ? (
          <AdminFormCard title={t('profile.captureBotTitle')} lead={t('profile.captureBotHint')}>
            <AppInputField
              label={t('org.captureBotDisplayName')}
              htmlFor="profile-capture-bot"
              type="text"
              value={captureBotName}
              maxLength={128}
              placeholder={t('profile.captureBotInherit', { value: me.capture_prefs.org_bot_display_name })}
              onChange={(e) => {
                setCaptureBotOk(false)
                setCaptureBotNameLocal(e.target.value)
              }}
            />
            <p className="muted">{t('org.captureBotDisplayNameHint')}</p>
            <p className="muted">{t('profile.captureBotPreview', { name: captureBotEffective })}</p>
            <AdminFormActions className="profile-actions">
              <AppSubmitButton ready={captureBotDirty} onClick={() => void saveCaptureBotPrefs()}>
                {t('common.save')}
              </AppSubmitButton>
              {captureBotOk ? <p className="ok">{t('profile.saved')}</p> : null}
            </AdminFormActions>
          </AdminFormCard>
        ) : null}

        <AdminFormCard title={t('profile.dateTimeTitle')} lead={t('profile.dateTimeHint')}>
          <AppSelectField
            label={t('profile.dateTimeFormat')}
            htmlFor="profile-dt-format"
            value={dateTimeFormat}
            onValueChange={(next) => {
              setDateTimeOk(false)
              setDateTimeFormatLocal(next as 'inherit' | DateTimeFormatId)
            }}
            options={[
              {
                value: 'inherit',
                label: t('profile.dateTimeInherit', {
                  value: t(`dateTime.format.${me?.date_time_prefs.instance_format ?? 'eu_24h'}`),
                }),
              },
              ...DATE_TIME_FORMATS.map((id) => ({ value: id, label: t(`dateTime.format.${id}`) })),
            ]}
          />
          <AppSelectField
            label={t('profile.timezone')}
            htmlFor="profile-timezone"
            value={timezone}
            onValueChange={(next) => {
              setDateTimeOk(false)
              setTimezoneLocal(next)
            }}
            options={[
              {
                value: 'inherit',
                label: t('profile.dateTimeInherit', {
                  value: me?.date_time_prefs.instance_timezone ?? 'GMT+0',
                }),
              },
              ...TIMEZONE_OPTIONS.map((tz) => ({ value: tz, label: tz })),
              ...(timezone !== 'inherit' &&
              !TIMEZONE_OPTIONS.includes(timezone as (typeof TIMEZONE_OPTIONS)[number])
                ? [{ value: timezone, label: timezone }]
                : []),
            ]}
          />
          <p className="muted">
            {t('profile.dateTimePreview', { sample: dateTimePreview })}
          </p>
          <AdminFormActions className="profile-actions">
            <AppSubmitButton ready={dateTimeDirty} onClick={() => void saveDateTimePrefs()}>
              {t('common.save')}
            </AppSubmitButton>
            {dateTimeOk ? <p className="ok">{t('profile.saved')}</p> : null}
          </AdminFormActions>
        </AdminFormCard>

        {showLocalAuth && me && (
          <AdminFormCard title={t('mfa.title')} lead={t('mfa.profileLead')}>
            {me.mfa_enabled ? (
              <form className="flex flex-col gap-3" onSubmit={(e) => void disableMfa(e)}>
                <p className="ok">{t('mfa.enabled')}</p>
                {me.mfa_required && <p className="muted">{t('mfa.requiredByOrg')}</p>}
                {!me.mfa_required && (
                  <>
                    <AppInputField
                      label={t('common.password')}
                      htmlFor="profile-mfa-disable-pw"
                      type="password"
                      required
                      value={disablePw}
                      onChange={(e) => setDisablePw(e.target.value)}
                      autoComplete="current-password"
                    />
                    <AppInputField
                      label={t('mfa.codeOrRecovery')}
                      htmlFor="profile-mfa-disable-code"
                      type="text"
                      required
                      value={disableCode}
                      onChange={(e) => setDisableCode(e.target.value)}
                    />
                    <Button variant="destructive" disabled={mfaBusy} type="submit">
                      {t('mfa.disable')}
                    </Button>
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
            <form className="flex flex-col gap-3" onSubmit={(e) => void changePw(e)}>
              <AppInputField
                label={t('auth.currentPassword')}
                htmlFor="profile-current-pw"
                type="password"
                required
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                autoComplete="current-password"
              />
              <AppInputField
                label={t('auth.newPassword')}
                htmlFor="profile-new-pw"
                type="password"
                required
                minLength={8}
                value={next}
                onChange={(e) => setNext(e.target.value)}
                autoComplete="new-password"
              />
              <AdminFormActions className="profile-actions">
                <AppSubmitButton type="submit" ready={passwordReady}>
                  {t('common.save')}
                </AppSubmitButton>
                {ok ? <p className="ok">{t('profile.saved')}</p> : null}
              </AdminFormActions>
            </form>
          </AdminFormCard>
        )}

        {hasOrg && (
          <AdminFormCard className="profile-backup-card" title={t('profile.backup')} lead={t('profile.backupLead')}>
            <div className="profile-backup-body">
            <div className="profile-backup-group">
              <span className="profile-backup-label">{t('profile.backupInclude')}</span>
              <div className="profile-backup-checks flex flex-col gap-1">
                <AppCheckboxRow
                  id="profile-backup-transcripts"
                  label={t('library.transcripts')}
                  checked={backupTranscripts}
                  onCheckedChange={setBackupTranscripts}
                />
                <AppCheckboxRow
                  id="profile-backup-summaries"
                  label={t('library.summaries')}
                  checked={backupSummaries}
                  onCheckedChange={setBackupSummaries}
                />
                <AppCheckboxRow
                  id="profile-backup-skills"
                  label={t('nav.skills')}
                  checked={backupSkills}
                  onCheckedChange={setBackupSkills}
                />
              </div>
            </div>
            <div className="profile-backup-group">
              <span className="profile-backup-label" id="profile-backup-format-label">
                {t('profile.backupFormat')}
              </span>
              <RadioGroup
                className="profile-backup-format-group"
                aria-labelledby="profile-backup-format-label"
                value={backupFormat}
                onValueChange={(value) => setBackupFormat(value as 'zip' | 'tgz')}
              >
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="zip" id="profile-backup-format-zip" />
                  <Label htmlFor="profile-backup-format-zip" className="font-normal">
                    ZIP
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="tgz" id="profile-backup-format-tgz" />
                  <Label htmlFor="profile-backup-format-tgz" className="font-normal">
                    tar.gz
                  </Label>
                </div>
              </RadioGroup>
            </div>
            </div>
            <p className="profile-backup-restore-hint">{t('profile.restoreBackupHint')}</p>
            <div className="profile-actions profile-backup-actions">
            <Button
              type="button"
              variant="outline"
              disabled={backingUp || (!backupTranscripts && !backupSummaries && !backupSkills)}
              onClick={() => void downloadBackup()}
            >
              {backingUp ? t('common.loading') : t('profile.downloadBackup')}
            </Button>
            <input
              ref={restoreInputRef}
              type="file"
              accept=".zip,.tgz,.tar.gz,application/zip,application/gzip"
              className="profile-backup-file-input"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void restoreBackup(file)
              }}
            />
            <Button
              type="button"
              variant="outline"
              disabled={restoringUp || backingUp}
              onClick={() => restoreInputRef.current?.click()}
            >
              {restoringUp ? t('common.loading') : t('profile.restoreBackup')}
            </Button>
            {restoreMessage && <p className="ok">{restoreMessage}</p>}
            </div>
          </AdminFormCard>
        )}
      </div>

      <AdminTableCard title={t('profile.tokens')} lead={t('profile.tokensLead')}>
        <p className="muted profile-mcp-hint">{t('profile.mcpOAuthHint')}</p>
        {!apiAllowed && (
          <div className="profile-alert" role="status">
            {t('profile.apiDisabled')}
          </div>
        )}

        {secret && (
          <div className="profile-secret-card">
            <p className="profile-secret-title">{t('profile.secretOnce')}</p>
            <AppUrlCopyRow value={secret} className="profile-secret-copy-row" />
          </div>
        )}

        {tokenTotpOpen && (
          <div className="profile-secret-card flex flex-col gap-3">
            <p className="profile-secret-title">{t('mfa.tokenStepUp')}</p>
            <AppInputField
              label={t('mfa.code')}
              htmlFor="profile-token-totp"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={tokenTotp}
              onChange={(e) => setTokenTotp(e.target.value)}
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" disabled={creating || !tokenTotp.trim()} onClick={() => void createToken(tokenTotp.trim())}
              >
                {creating ? t('common.loading') : t('profile.newToken')}
              </Button>
              <Button type="button" variant="outline" onClick={() => { setTokenTotpOpen(false); setTokenTotp('') }}>
                {t('common.cancel')}
              </Button>
            </div>
          </div>
        )}

        <div className="profile-token-create">
          <AppInputField
            className="grow"
            label={t('profile.tokenName')}
            htmlFor="profile-token-name"
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
          <AppSubmitButton
            ready={apiAllowed && !creating && Boolean(tokenName.trim())}
            busy={creating}
            onClick={() => void createToken()}
          >
            {creating ? t('common.loading') : t('profile.newToken')}
          </AppSubmitButton>
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
                    {tok.revoked ? <HubBadge tone="muted">{t('profile.revoked')}</HubBadge> : null}
                    {tok.blocked_by_tariff ? <HubBadge tone="pending">{t('profile.blockedTariff')}</HubBadge> : null}
                  </div>
                </div>
                {!tok.revoked && (
                  <Button type="button" variant="destructive" onClick={() => void revoke(tok.id)}>
                    {t('profile.revoke')}
                  </Button>
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
          <Button type="button" variant="destructive" onClick={() => void openDeleteAccount()}>
            {t('profile.deleteAccount')}
          </Button>
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
              <AppSelectField
                label={t('profile.deleteAccountSuccessor')}
                htmlFor="profile-delete-successor"
                required
                value={deleteSuccessor}
                disabled={deleteBusy}
                onValueChange={setDeleteSuccessor}
                options={[
                  ...(deletePreview.candidates.length > 1 ? [{ value: '', label: t('org.target') }] : []),
                  ...deletePreview.candidates.map((c) => ({ value: c.id, label: c.email })),
                ]}
              />
            </>
          )}
          {showLocalAuthDelete && (
            <AppInputField
              label={t('profile.deleteAccountPassword')}
              htmlFor="profile-delete-pw"
              type="password"
              required
              autoComplete="current-password"
              value={deletePassword}
              disabled={deleteBusy}
              onChange={(e) => setDeletePassword(e.target.value)}
            />
          )}
          {me?.mfa_enabled && (
            <AppInputField
              label={t('profile.deleteAccountTotp')}
              htmlFor="profile-delete-totp"
              type="text"
              required
              autoComplete="one-time-code"
              value={deleteTotp}
              disabled={deleteBusy}
              onChange={(e) => setDeleteTotp(e.target.value)}
            />
          )}
          <div className="flex flex-wrap items-center gap-2 modal-actions">
            <Button type="button" variant="destructive" disabled={ deleteBusy || (deletePreview.requires_successor && !deleteSuccessor) || (showLocalAuthDelete && !deletePassword) || (Boolean(me?.mfa_enabled) && !deleteTotp.trim()) } onClick={() => void confirmDeleteAccount()}
            >
              {deleteBusy ? t('profile.deleteAccountBusy') : t('profile.deleteAccountConfirm')}
            </Button>
            <Button type="button" disabled={deleteBusy} onClick={() => setDeleteOpen(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </Modal>
      )}

    </AdminPage>
  )
}
