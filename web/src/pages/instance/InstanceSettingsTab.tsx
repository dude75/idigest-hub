import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '../../api'
import { useAuth } from '../../auth'
import type { InstanceSettings } from '../../types'
import { AdminPage } from '../../components/AdminSection'
import { isAvailableSummarizeModel } from '../../summarizeModels'
import { diarizationOptionsForAsr, isDispatchableCombo } from '../../transcribeModels'
import { showError } from '../../util'
import { DATE_TIME_FORMATS } from '../../util/datetimeFormat'
import { TIMEZONE_OPTIONS } from '../../util/timezones'
import {
  DEFAULT_IMPORT_AUDIO_BITRATE_KBPS,
  DEFAULT_IMPORT_MAX_CONCURRENT,
  IMPORT_MAX_CONCURRENT_MAX,
} from './constants'

export function InstanceSettingsTab() {
  const { t } = useTranslation()
  const { me, refresh } = useAuth()
  const [settings, setSettings] = useState<InstanceSettings | null>(null)
  const [smtpPassword, setSmtpPassword] = useState('')
  const [proxyPassword, setProxyPassword] = useState('')
  const [smtpTestEmail, setSmtpTestEmail] = useState('')
  const [smtpTestingConnection, setSmtpTestingConnection] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)

  function normalizeSettings(data: InstanceSettings): InstanceSettings {
    return {
      ...data,
      date_time_format: data.date_time_format ?? 'eu_24h',
      timezone: data.timezone ?? 'GMT+0',
      asr_models: data.asr_models ?? [],
      diarization_models: data.diarization_models ?? [],
      summarize_models: data.summarize_models ?? [],
      summarize_model: data.summarize_model ?? null,
      import_audio_bitrate_kbps: data.import_audio_bitrate_kbps ?? DEFAULT_IMPORT_AUDIO_BITRATE_KBPS,
      import_max_concurrent: data.import_max_concurrent ?? DEFAULT_IMPORT_MAX_CONCURRENT,
      capture_connectors: data.capture_connectors ?? [],
      smtp_password_configured: data.smtp_password_configured ?? false,
    }
  }

  async function load() {
    try {
      const data = await api<InstanceSettings>('/instance/settings')
      const normalized = normalizeSettings(data)
      setSettings(normalized)
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const availableDiarizationModels = useMemo(() => {
    if (!settings) return []
    return diarizationOptionsForAsr(settings, settings.asr_model)
  }, [settings])

  const serviceModelsValid = useMemo(() => {
    if (!settings) return true
    const transcribeOk = isDispatchableCombo(settings, settings.asr_model, settings.diarization_model)
    const summarizeOk = isAvailableSummarizeModel(settings, settings.summarize_model)
    return transcribeOk && summarizeOk
  }, [settings])

  function smtpTestPayload() {
    if (!settings) return null
    const payload: Record<string, string | number | boolean> = {}
    const host = (settings.smtp_host || '').trim()
    const user = (settings.smtp_user || '').trim()
    const from = (settings.smtp_from || '').trim()
    if (host) payload.smtp_host = host
    if (settings.smtp_port != null) payload.smtp_port = settings.smtp_port
    if (user) payload.smtp_user = user
    if (from) payload.smtp_from = from
    payload.smtp_tls = settings.smtp_tls
    if (smtpPassword) payload.smtp_password = smtpPassword
    return payload
  }

  function smtpPasswordReady() {
    return Boolean(smtpPassword || settings?.smtp_password_configured)
  }

  async function testSmtpSend() {
    const payload = smtpTestPayload()
    if (!payload) return false
    const to = smtpTestEmail.trim() || me?.user.email || ''
    if (!to) return false
    try {
      const result = await api<{ to: string }>('/instance/smtp/test-send', {
        method: 'POST',
        body: JSON.stringify({ ...payload, to }),
      })
      toast.success(t('instance.smtpTestSendOk', { email: result.to }))
      return true
    } catch (e) {
      showError(e)
      return false
    }
  }

  async function testSmtpConnection() {
    const payload = smtpTestPayload()
    if (!payload) return
    setSmtpTestingConnection(true)
    try {
      await api('/instance/smtp/test-connection', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      toast.success(t('instance.smtpTestConnectionOk'))
      if (smtpPasswordReady()) {
        await testSmtpSend()
      }
    } catch (e) {
      showError(e)
    } finally {
      setSmtpTestingConnection(false)
    }
  }

  async function saveSettings() {
    if (!settings) return
    setSaveBusy(true)
    try {
      const data = await api<InstanceSettings>('/instance/settings', {
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
          summarize_model: settings.summarize_model,
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
          rate_limit_mcp_poll_user: settings.rate_limit_mcp_poll_user,
          rate_limit_oauth_register_ip: settings.rate_limit_oauth_register_ip,
          rate_limit_oauth_register_global: settings.rate_limit_oauth_register_global,
          rate_limit_oauth_token_ip: settings.rate_limit_oauth_token_ip,
          rate_limit_oauth_token_global: settings.rate_limit_oauth_token_global,
          import_enabled: settings.import_enabled,
          import_allowed_extractors: settings.import_platforms.filter((p) => p.enabled).map((p) => p.id),
          download_proxy_url: settings.download_proxy_url,
          download_proxy_enabled: settings.download_proxy_enabled,
          download_cookies_path: settings.download_cookies_path,
          import_audio_bitrate_kbps: settings.import_audio_bitrate_kbps ?? DEFAULT_IMPORT_AUDIO_BITRATE_KBPS,
          import_max_concurrent: settings.import_max_concurrent ?? DEFAULT_IMPORT_MAX_CONCURRENT,
          capture_enabled: settings.capture_enabled,
          capture_allowed_connectors: settings.capture_connectors.filter((c) => c.enabled).map((c) => c.id),
          session_ttl_hours: settings.session_ttl_hours,
          date_time_format: settings.date_time_format,
          timezone: settings.timezone,
          ...(smtpPassword ? { smtp_password: smtpPassword } : {}),
          ...(proxyPassword ? { download_proxy_password: proxyPassword } : {}),
        }),
      })
      const normalized = normalizeSettings(data)
      setSettings(normalized)
      setSmtpPassword('')
      setProxyPassword('')
      toast.success(t('profile.saved'))
      await refresh()
    } catch (e) {
      showError(e)
    } finally {
      setSaveBusy(false)
    }
  }

  if (!settings) return null

  return (
    <AdminPage>
      <div className="org-settings-stack">
      <details className="fold org-fold card">
        <summary className="org-fold-summary">
          <span>{t('instance.baseTitle')}</span>
        </summary>
        <div className="stack fold-body">
          <label className="row">
            <input type="checkbox" checked={settings.allow_new_orgs} onChange={(e) => setSettings({ ...settings, allow_new_orgs: e.target.checked })} />
            {t('instance.allowNewOrgs')}
          </label>
          <label>{t('instance.publicBaseUrl')}<input value={settings.public_base_url || ''} onChange={(e) => setSettings({ ...settings, public_base_url: e.target.value })} /></label>
          <label>
            {t('instance.sessionTtlHours')}
            <input
              type="number"
              min={1}
              max={336}
              value={settings.session_ttl_hours}
              onChange={(e) => setSettings({ ...settings, session_ttl_hours: Number(e.target.value) || 1 })}
            />
          </label>
          <p className="muted">{t('instance.sessionTtlHint')}</p>
        </div>
      </details>

      <details className="fold org-fold card">
        <summary className="org-fold-summary">
          <span>{t('instance.serviceModelsTitle')}</span>
        </summary>
        <div className="stack fold-body">
          <p className="muted">{t('instance.serviceModelsHint')}</p>
          <label>
            {t('instance.asr')}
            <select
              value={settings.asr_model}
              onChange={(e) => {
                const nextAsr = e.target.value
                const allowedDiar = diarizationOptionsForAsr(settings, nextAsr)
                const nextDiar =
                  settings.diarization_model && allowedDiar.includes(settings.diarization_model)
                    ? settings.diarization_model
                    : null
                setSettings({ ...settings, asr_model: nextAsr, diarization_model: nextDiar })
              }}
              disabled={settings.asr_models.length === 0}
            >
              {settings.asr_models.length === 0 ? (
                <option value={settings.asr_model}>{settings.asr_model}</option>
              ) : (
                settings.asr_models.map((modelId) => (
                  <option key={modelId} value={modelId}>{modelId}</option>
                ))
              )}
            </select>
          </label>
          <label>
            {t('instance.diarization')}
            <select
              value={settings.diarization_model || ''}
              onChange={(e) => setSettings({ ...settings, diarization_model: e.target.value || null })}
              disabled={settings.diarization_models.length === 0}
            >
              <option value="">{t('instance.diarizationOff')}</option>
              {availableDiarizationModels.map((modelId) => (
                <option key={modelId} value={modelId}>{modelId}</option>
              ))}
            </select>
          </label>
          <label>
            {t('instance.summarizeModelLabel')}
            <select
              value={settings.summarize_model || ''}
              onChange={(e) => setSettings({ ...settings, summarize_model: e.target.value || null })}
              disabled={settings.summarize_models.length === 0}
            >
              <option value="">{t('instance.summarizeModelUnset')}</option>
              {settings.summarize_models.length === 0 ? (
                settings.summarize_model ? (
                  <option value={settings.summarize_model}>{settings.summarize_model}</option>
                ) : null
              ) : (
                settings.summarize_models.map((modelId) => (
                  <option key={modelId} value={modelId}>{modelId}</option>
                ))
              )}
            </select>
          </label>
          {!serviceModelsValid ? <p className="err">{t('instance.serviceModelsInvalid')}</p> : null}
        </div>
      </details>

      <details className="fold org-fold card">
        <summary className="org-fold-summary">
          <span>{t('instance.smtpTitle')}</span>
        </summary>
        <div className="stack fold-body">
          <label>{t('instance.smtpHost')}<input value={settings.smtp_host || ''} onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value })} /></label>
          <label>{t('instance.smtpPort')}<input type="number" value={settings.smtp_port ?? ''} onChange={(e) => setSettings({ ...settings, smtp_port: e.target.value ? Number(e.target.value) : null })} /></label>
          <label>{t('instance.smtpUser')}<input value={settings.smtp_user || ''} onChange={(e) => setSettings({ ...settings, smtp_user: e.target.value })} /></label>
          <label>
            {t('instance.smtpPassword')}
            <input
              type="password"
              value={smtpPassword}
              placeholder={settings.smtp_password_configured ? t('instance.smtpPasswordSaved') : ''}
              onChange={(e) => setSmtpPassword(e.target.value)}
            />
          </label>
          <p className="muted">
            {settings.smtp_password_configured && !smtpPassword
              ? t('instance.smtpPasswordSavedHint')
              : t('instance.smtpPasswordHint')}
          </p>
          <label>{t('instance.smtpFrom')}<input value={settings.smtp_from || ''} onChange={(e) => setSettings({ ...settings, smtp_from: e.target.value })} /></label>
          <label className="row">
            <input type="checkbox" checked={settings.smtp_tls} onChange={(e) => setSettings({ ...settings, smtp_tls: e.target.checked })} />
            {t('instance.smtpTls')}
          </label>
          <label>
            {t('instance.smtpTestEmail')}
            <input
              type="email"
              value={smtpTestEmail}
              placeholder={me?.user.email || ''}
              onChange={(e) => setSmtpTestEmail(e.target.value)}
            />
          </label>
          <p className="muted">{t('instance.smtpTestEmailHint')}</p>
          <button
            type="button"
            disabled={smtpTestingConnection || !(settings.smtp_host || '').trim() || !(settings.smtp_from || '').trim()}
            onClick={() => void testSmtpConnection()}
          >
            {smtpTestingConnection ? t('instance.smtpTestingConnection') : t('instance.smtpTestConnection')}
          </button>
        </div>
      </details>

      <details className="fold org-fold card">
        <summary className="org-fold-summary">
          <span>{t('instance.importTitle')}</span>
        </summary>
        <div className="stack fold-body">
          <label className="row">
            <input
              type="checkbox"
              checked={settings.import_enabled}
              onChange={(e) => setSettings({ ...settings, import_enabled: e.target.checked })}
            />
            {t('instance.importEnabled')}
          </label>
          <label>
            {t('instance.downloadProxyUrl')}
            <input
              value={settings.download_proxy_url || ''}
              onChange={(e) => {
                const url = e.target.value || null
                setSettings({
                  ...settings,
                  download_proxy_url: url,
                  download_proxy_enabled: url ? settings.download_proxy_enabled : false,
                })
              }}
              placeholder="socks5://host:1080 or http://host:8080"
            />
          </label>
          <p className="muted">{t('instance.downloadProxyHint')}</p>
          <label className="row">
            <input
              type="checkbox"
              checked={settings.download_proxy_enabled}
              disabled={
                !settings.import_enabled ||
                !(settings.download_proxy_configured || (settings.download_proxy_url || '').trim())
              }
              onChange={(e) => setSettings({ ...settings, download_proxy_enabled: e.target.checked })}
            />
            {t('instance.downloadProxyEnabled')}
          </label>
          <p className="muted">{t('instance.downloadProxyEnabledHint')}</p>
          <label>
            {t('instance.downloadProxyPassword')}
            <input type="password" value={proxyPassword} onChange={(e) => setProxyPassword(e.target.value)} />
          </label>
          <label>
            {t('instance.downloadCookiesPath')}
            <input
              value={settings.download_cookies_path || ''}
              onChange={(e) => setSettings({ ...settings, download_cookies_path: e.target.value || null })}
              placeholder="/data/youtube-cookies.txt"
            />
          </label>
          <p className="muted">{t('instance.downloadCookiesHint')}</p>
          <label>
            {t('instance.importAudioBitrate')}
            <input
              type="number"
              min={0}
              max={320}
              placeholder={String(DEFAULT_IMPORT_AUDIO_BITRATE_KBPS)}
              value={settings.import_audio_bitrate_kbps ?? ''}
              disabled={!settings.import_enabled}
              onChange={(e) => {
                const raw = e.target.value
                setSettings({
                  ...settings,
                  import_audio_bitrate_kbps:
                    raw === '' ? (undefined as unknown as number) : Math.max(0, Number(raw) || 0),
                })
              }}
            />
          </label>
          <p className="muted">{t('instance.importAudioBitrateHint')}</p>
          <label>
            {t('instance.importMaxConcurrent')}
            <input
              type="number"
              min={1}
              max={IMPORT_MAX_CONCURRENT_MAX}
              value={settings.import_max_concurrent ?? DEFAULT_IMPORT_MAX_CONCURRENT}
              disabled={!settings.import_enabled}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  import_max_concurrent: Math.min(
                    IMPORT_MAX_CONCURRENT_MAX,
                    Math.max(1, Number(e.target.value) || DEFAULT_IMPORT_MAX_CONCURRENT),
                  ),
                })
              }
            />
          </label>
          <p className="muted">{t('instance.importMaxConcurrentHint')}</p>
          <p className="muted">{t('instance.importPlatformsHint')}</p>
          <div className="stack">
            {settings.import_platforms.map((platform) => (
              <label className="row" key={platform.id}>
                <input
                  type="checkbox"
                  checked={platform.enabled}
                  disabled={!settings.import_enabled}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      import_platforms: settings.import_platforms.map((item) =>
                        item.id === platform.id ? { ...item, enabled: e.target.checked } : item,
                      ),
                    })
                  }
                />
                <span className="grow">
                  <strong>{platform.label}</strong>
                  <span className="muted"> — {platform.domains.join(', ')}</span>
                </span>
              </label>
            ))}
          </div>
          <div className="row">
            <button
              type="button"
              disabled={!settings.import_enabled}
              onClick={() =>
                setSettings({
                  ...settings,
                  import_platforms: settings.import_platforms.map((item) => ({ ...item, enabled: true })),
                })
              }
            >
              {t('instance.importSelectAll')}
            </button>
            <button
              type="button"
              disabled={!settings.import_enabled}
              onClick={() =>
                setSettings({
                  ...settings,
                  import_platforms: settings.import_platforms.map((item) => ({
                    ...item,
                    enabled: ['Youtube', 'Rutube', 'TikTok'].includes(item.id),
                  })),
                })
              }
            >
              {t('instance.importResetDefaults')}
            </button>
          </div>
        </div>
      </details>

      <details className="fold org-fold card">
        <summary className="org-fold-summary">
          <span>{t('instance.captureTitle')}</span>
        </summary>
        <div className="stack fold-body">
          <label className="row">
            <input
              type="checkbox"
              checked={settings.capture_enabled}
              onChange={(e) => setSettings({ ...settings, capture_enabled: e.target.checked })}
            />
            {t('instance.captureEnabled')}
          </label>
          <p className="muted">{t('instance.captureConnectorsHint')}</p>
          <div className="stack">
            {settings.capture_connectors.length === 0 ? (
              <p className="muted">{t('instance.captureConnectorsEmpty')}</p>
            ) : null}
            {settings.capture_connectors.map((connector) => (
              <label className="row" key={connector.id}>
                <input
                  type="checkbox"
                  checked={connector.enabled}
                  disabled={!settings.capture_enabled || connector.status === 'unavailable'}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      capture_connectors: settings.capture_connectors.map((item) =>
                        item.id === connector.id ? { ...item, enabled: e.target.checked } : item,
                      ),
                    })
                  }
                />
                <span className="grow">
                  <strong>{connector.label}</strong>
                  {connector.status && connector.status !== 'loaded' ? (
                    <span className="muted"> — {connector.status}</span>
                  ) : null}
                </span>
              </label>
            ))}
          </div>
        </div>
      </details>

      <details className="fold org-fold card">
        <summary className="org-fold-summary">
          <span>{t('instance.dateTimeTitle')}</span>
        </summary>
        <div className="stack fold-body">
          <label>
            {t('instance.dateTimeFormat')}
            <select
              value={settings.date_time_format || 'eu_24h'}
              onChange={(e) => setSettings({ ...settings, date_time_format: e.target.value })}
            >
              {DATE_TIME_FORMATS.map((id) => (
                <option key={id} value={id}>
                  {t(`dateTime.format.${id}`)}
                </option>
              ))}
            </select>
          </label>
          <p className="muted">{t('instance.dateTimeFormatHint')}</p>
          <label>
            {t('instance.timezone')}
            <select
              value={settings.timezone || 'GMT+0'}
              onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
            >
              {TIMEZONE_OPTIONS.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </label>
          <p className="muted">{t('instance.timezoneHint')}</p>
        </div>
      </details>

      <details className="fold org-fold card">
        <summary className="org-fold-summary">
          <span>{t('instance.rateLimitTitle')}</span>
        </summary>
        <div className="stack fold-body">
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
            <p className="muted">{t('instance.rateLimitMcpHint')}</p>
            <label>{t('instance.rateLimitMcpPollPerUserMin')}<input type="number" min={0} value={settings.rate_limit_mcp_poll_user} onChange={(e) => setSettings({ ...settings, rate_limit_mcp_poll_user: Number(e.target.value) })} /></label>
          </fieldset>
          <fieldset className="stack" disabled={!settings.rate_limit_enabled}>
            <legend>{t('instance.rateLimitOAuth')}</legend>
            <label>{t('instance.rateLimitOAuthRegisterPerIpHour')}<input type="number" min={0} value={settings.rate_limit_oauth_register_ip} onChange={(e) => setSettings({ ...settings, rate_limit_oauth_register_ip: Number(e.target.value) })} /></label>
            <label>{t('instance.rateLimitOAuthRegisterGlobalHour')}<input type="number" min={0} value={settings.rate_limit_oauth_register_global} onChange={(e) => setSettings({ ...settings, rate_limit_oauth_register_global: Number(e.target.value) })} /></label>
            <label>{t('instance.rateLimitOAuthTokenPerIpMin')}<input type="number" min={0} value={settings.rate_limit_oauth_token_ip} onChange={(e) => setSettings({ ...settings, rate_limit_oauth_token_ip: Number(e.target.value) })} /></label>
            <label>{t('instance.rateLimitOAuthTokenGlobalMin')}<input type="number" min={0} value={settings.rate_limit_oauth_token_global} onChange={(e) => setSettings({ ...settings, rate_limit_oauth_token_global: Number(e.target.value) })} /></label>
          </fieldset>
        </div>
      </details>
      </div>

      <div className="card">
        <button
          className="primary"
          type="button"
          disabled={!serviceModelsValid || saveBusy}
          onClick={() => void saveSettings()}
        >
          {t('common.save')}
        </button>
      </div>
    </AdminPage>
  )
}
