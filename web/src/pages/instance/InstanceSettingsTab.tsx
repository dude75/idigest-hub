import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import type { InstanceSettings } from '../../types'
import { showError } from '../../util'
import { DEFAULT_IMPORT_AUDIO_BITRATE_KBPS } from './constants'

export function InstanceSettingsTab() {
  const { t } = useTranslation()
  const [settings, setSettings] = useState<InstanceSettings | null>(null)
  const [smtpPassword, setSmtpPassword] = useState('')
  const [proxyPassword, setProxyPassword] = useState('')

  async function load() {
    try {
      const data = await api<InstanceSettings>('/instance/settings')
      setSettings({
        ...data,
        import_audio_bitrate_kbps: data.import_audio_bitrate_kbps ?? DEFAULT_IMPORT_AUDIO_BITRATE_KBPS,
      })
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    void load()
  }, [])

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
        import_enabled: settings.import_enabled,
        import_allowed_extractors: settings.import_platforms.filter((p) => p.enabled).map((p) => p.id),
        download_proxy_url: settings.download_proxy_url,
        download_proxy_enabled: settings.download_proxy_enabled,
        download_cookies_path: settings.download_cookies_path,
        import_audio_bitrate_kbps: settings.import_audio_bitrate_kbps ?? DEFAULT_IMPORT_AUDIO_BITRATE_KBPS,
        ...(smtpPassword ? { smtp_password: smtpPassword } : {}),
        ...(proxyPassword ? { download_proxy_password: proxyPassword } : {}),
      }),
    })
    setSmtpPassword('')
    setProxyPassword('')
    await load()
  }

  if (!settings) return null

  return (
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
        <summary>{t('instance.importTitle')}</summary>
        <div className="stack">
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
  )
}
