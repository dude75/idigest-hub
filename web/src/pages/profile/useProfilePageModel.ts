import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { api, apiDownload, apiUpload } from '../../api'
import { useAuth } from '../../auth'
import {
  allowedDefaultRoutes,
  localAuthProfileVisible,
  normalizeDefaultRoute,
  type DefaultRoute,
} from '../../routes'
import type { SchemaApiTokenCreateResponse, SchemaApiTokenListResponse } from '../../openapi'
import type { ApiToken, DateTimeFormatId, DateTimePrefs } from '../../types'
import {
  isAvailableSummarizeModel,
  resolveEffectiveSummarizeModel,
} from '../../summarizeModels'
import {
  diarizationOptionsForAsr,
  isDispatchableCombo,
  resolveEffectiveAsr,
  resolveEffectiveDiarization,
} from '../../transcribeModels'
import { fmtDate, formatInteger, showError } from '../../util'
import { DATE_TIME_FORMATS, formatDateTime } from '../../util/datetimeFormat'

export type AccountDeletePreview = {
  requires_successor: boolean
  will_delete_org: boolean
  candidates: { id: string; email: string; role: string }[]
}

export function useProfilePageModel() {
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
  const [toneAnalytics, setToneAnalyticsLocal] = useState(true)
  const [transcribeOk, setTranscribeOk] = useState(false)
  const [summarizeModel, setSummarizeModelLocal] = useState<'inherit' | string>('inherit')
  const [summarizeOk, setSummarizeOk] = useState(false)
  const [captureBotName, setCaptureBotNameLocal] = useState('')
  const [captureBotOk, setCaptureBotOk] = useState(false)
  const [firstName, setFirstNameLocal] = useState('')
  const [lastName, setLastNameLocal] = useState('')
  const [namesSyncedFromMe, setNamesSyncedFromMe] = useState(false)
  const [namesOk, setNamesOk] = useState(false)
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
    const r = await api<SchemaApiTokenListResponse>('/auth/tokens')
    setTokens(r.items ?? [])
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
    if (!me) {
      setNamesSyncedFromMe(false)
      return
    }
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
    setToneAnalyticsLocal(me.user.tone_analytics_enabled ?? true)
    setSummarizeModelLocal(me.user.summarize_model || 'inherit')
    setCaptureBotNameLocal(me.user.capture_bot_display_name || '')
    setFirstNameLocal(me.user.first_name || '')
    setLastNameLocal(me.user.last_name || '')
    setNamesSyncedFromMe(true)
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
  const savedToneAnalytics = me?.user.tone_analytics_enabled ?? true
  const transcribeDirty =
    asrModel !== savedAsrModel ||
    diarizationModel !== savedDiarizationModel ||
    toneAnalytics !== savedToneAnalytics
  const onlyTonePrefDirty =
    toneAnalytics !== savedToneAnalytics &&
    asrModel === savedAsrModel &&
    diarizationModel === savedDiarizationModel
  const transcribeReady = transcribeDirty && (onlyTonePrefDirty || transcribeComboValid)
  const tariffAllowsTone = Boolean(me?.org?.tariff.tone_analytics_enabled)

  const savedSummarizeModel = me?.user.summarize_model || 'inherit'
  const summarizeDirty = summarizeModel !== savedSummarizeModel
  const summarizeReady = summarizeDirty && summarizeModelValid

  const savedCaptureBotName = me?.user.capture_bot_display_name ?? ''
  const captureBotDirty = captureBotName.trim() !== savedCaptureBotName.trim()

  const savedFirstName = me?.user.first_name ?? ''
  const savedLastName = me?.user.last_name ?? ''
  const namesDirty =
    namesSyncedFromMe &&
    (firstName.trim() !== (savedFirstName || '').trim() || lastName.trim() !== (savedLastName || '').trim())

  const passwordReady = current.trim().length > 0 && next.trim().length >= 8

  const showTranscribeSection = Boolean(
    me &&
      (me.transcribe_models.asr_models.length > 0 ||
        me.transcribe_models.diarization_models.length > 0 ||
        me.org),
  )
  const showSummarizeSection = Boolean(me && me.summarize_models.summarize_models.length > 0)
  const showCaptureSection = Boolean(me?.capture_prefs.capture_enabled)
  const showModelsTab = showTranscribeSection || showSummarizeSection || showCaptureSection

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
          diarization_model:
            diarizationModel === 'inherit' ? null : diarizationModel === 'off' ? '' : diarizationModel,
          tone_analytics_enabled: toneAnalytics,
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

  async function saveProfileNames() {
    setNamesOk(false)
    setCaptureBotOk(false)
    setSummarizeOk(false)
    setTranscribeOk(false)
    setRouteOk(false)
    setOk(false)
    setDateTimeOk(false)
    try {
      await api('/me', {
        method: 'PATCH',
        body: JSON.stringify({
          first_name: firstName.trim() ? firstName.trim() : null,
          last_name: lastName.trim() ? lastName.trim() : null,
        }),
      })
      await refresh()
      setNamesOk(true)
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
      const row = await api<SchemaApiTokenCreateResponse>('/auth/tokens', {
        method: 'POST',
        body: JSON.stringify(body),
      })
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

  return {
    t,
    me,
    refresh,
    nav,
    orgLabel,
    mfaSummary,
    hasOrg,
    showLocalAuth,
    showLocalAuthDelete,
    apiAllowed,
    activeTokens,
    tokens,
    canDeleteAccount,
    showModelsTab,
    showTranscribeSection,
    showSummarizeSection,
    showCaptureSection,
    firstName,
    setFirstNameLocal,
    lastName,
    setLastNameLocal,
    namesDirty,
    namesOk,
    setNamesOk,
    saveProfileNames,
    defaultRoute,
    setDefaultRouteLocal,
    defaultRouteDirty,
    routeOk,
    setRouteOk,
    saveDefaultRoute,
    dateTimeFormat,
    setDateTimeFormatLocal,
    timezone,
    setTimezoneLocal,
    dateTimePreview,
    dateTimeDirty,
    dateTimeOk,
    setDateTimeOk,
    saveDateTimePrefs,
    asrModel,
    setAsrModelLocal,
    diarizationModel,
    setDiarizationModelLocal,
    toneAnalytics,
    setToneAnalyticsLocal,
    availableDiarizationModels,
    transcribeComboValid,
    transcribeReady,
    transcribeOk,
    setTranscribeOk,
    tariffAllowsTone,
    saveTranscribePrefs,
    summarizeModel,
    setSummarizeModelLocal,
    summarizeModelValid,
    summarizeReady,
    summarizeOk,
    setSummarizeOk,
    saveSummarizePrefs,
    captureBotName,
    setCaptureBotNameLocal,
    captureBotDirty,
    captureBotOk,
    setCaptureBotOk,
    captureBotEffective,
    saveCaptureBotPrefs,
    current,
    setCurrent,
    next,
    setNext,
    passwordReady,
    ok,
    changePw,
    disablePw,
    setDisablePw,
    disableCode,
    setDisableCode,
    mfaBusy,
    disableMfa,
    tokenName,
    setTokenName,
    secret,
    creating,
    createToken,
    tokenTotp,
    setTokenTotp,
    tokenTotpOpen,
    setTokenTotpOpen,
    revoke,
    backupTranscripts,
    setBackupTranscripts,
    backupSummaries,
    setBackupSummaries,
    backupSkills,
    setBackupSkills,
    backupFormat,
    setBackupFormat,
    backingUp,
    restoringUp,
    restoreMessage,
    restoreInputRef,
    downloadBackup,
    restoreBackup,
    deleteOpen,
    setDeleteOpen,
    deletePreview,
    deletePassword,
    setDeletePassword,
    deleteTotp,
    setDeleteTotp,
    deleteSuccessor,
    setDeleteSuccessor,
    deleteBusy,
    openDeleteAccount,
    confirmDeleteAccount,
    fmtDate,
    formatInteger,
  }
}

export type ProfilePageModel = ReturnType<typeof useProfilePageModel>
