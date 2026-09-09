import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { api, apiDownload } from '../api'
import { useAuth } from '../auth'
import { allowedDefaultRoutes, defaultRouteLabel, normalizeDefaultRoute, type DefaultRoute } from '../routes'
import type { ApiToken } from '../types'
import { fmtDate, showError } from '../util'

export function ProfilePage() {
  const { t } = useTranslation()
  const { me, refresh, setDefaultRoute } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [tokens, setTokens] = useState<ApiToken[]>([])
  const [tokenName, setTokenName] = useState('')
  const [secret, setSecret] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [creating, setCreating] = useState(false)
  const [ok, setOk] = useState(false)
  const [routeOk, setRouteOk] = useState(false)
  const [defaultRoute, setDefaultRouteLocal] = useState<DefaultRoute>(() => {
    const stored = normalizeDefaultRoute(me?.user.default_route)
    const allowed = allowedDefaultRoutes(me)
    return stored && allowed.includes(stored) ? stored : allowed[0]
  })

  const hasOrg = Boolean(me?.org)
  const apiAllowed = !me?.org || Boolean(me.org.tariff.api_enabled)
  const activeTokens = tokens.filter((tok) => !tok.revoked)
  const [backupTranscripts, setBackupTranscripts] = useState(true)
  const [backupSummaries, setBackupSummaries] = useState(true)
  const [backupSkills, setBackupSkills] = useState(true)
  const [backupFormat, setBackupFormat] = useState<'zip' | 'tgz'>('zip')
  const [backingUp, setBackingUp] = useState(false)

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
  }, [me])

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

  async function createToken() {
    const name = tokenName.trim()
    if (!name || !apiAllowed) return
    setCopied(false)
    setCreating(true)
    try {
      const row = await api<ApiToken>('/auth/tokens', { method: 'POST', body: JSON.stringify({ name }) })
      setSecret(row.token || null)
      setTokenName('')
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setCreating(false)
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

  return (
    <div className="profile-page">
      <header className="profile-head">
        <div>
          <h1>{t('profile.title')}</h1>
          <p className="muted profile-email">{me?.user.email}</p>
        </div>
      </header>

      <div className="profile-grid">
        <section className="card stack profile-section">
          <div className="profile-section-head">
            <h2>{t('profile.defaultRoute')}</h2>
            <p className="muted profile-section-lead">{t('profile.defaultRouteHint')}</p>
          </div>
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
        </section>

        <form className="card stack profile-section" onSubmit={(e) => void changePw(e)}>
          <div className="profile-section-head">
            <h2>{t('auth.changePassword')}</h2>
          </div>
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

        {hasOrg && (
          <section className="card stack profile-section profile-backup">
            <div className="profile-section-head">
              <h2>{t('profile.backup')}</h2>
              <p className="muted profile-section-lead">{t('profile.backupLead')}</p>
            </div>
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
                <div className="profile-backup-formats" role="radiogroup" aria-label={t('profile.backupFormat')}>
                  <button
                    type="button"
                    className={backupFormat === 'zip' ? 'active' : ''}
                    role="radio"
                    aria-checked={backupFormat === 'zip'}
                    onClick={() => setBackupFormat('zip')}
                  >
                    ZIP
                  </button>
                  <button
                    type="button"
                    className={backupFormat === 'tgz' ? 'active' : ''}
                    role="radio"
                    aria-checked={backupFormat === 'tgz'}
                    onClick={() => setBackupFormat('tgz')}
                  >
                    TGZ
                  </button>
                </div>
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
          </section>
        )}

        <section className="card stack profile-section profile-tokens">
          <div className="profile-section-head">
            <h2>{t('profile.tokens')}</h2>
            <p className="muted profile-section-lead">{t('profile.tokensLead')}</p>
          </div>

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
            <p className="muted profile-empty">{t('profile.noTokens')}</p>
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
        </section>
      </div>
    </div>
  )
}
