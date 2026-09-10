import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { isOrgAdmin, useAuth } from '../auth'
import { TariffDetails } from '../components/TariffDetails'
import { LIBRARY_DEFAULT } from '../routes'
import type { Org, OrgSsoAdmin, Tariff, User } from '../types'
import { showError, WalletLabel } from '../util'

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
  const [tariffId, setTariffId] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'org_admin' | 'org_member'>('org_member')
  const [offUser, setOffUser] = useState<User | null>(null)
  const [action, setAction] = useState<'transfer' | 'wipe'>('wipe')
  const [target, setTarget] = useState('')
  const [tempPw, setTempPw] = useState<string | null>(null)
  const [sso, setSso] = useState<OrgSsoAdmin | null>(null)
  const [ssoIssuer, setSsoIssuer] = useState('')
  const [ssoClientId, setSsoClientId] = useState('')
  const [ssoClientSecret, setSsoClientSecret] = useState('')
  const [ssoEnabled, setSsoEnabled] = useState(false)
  const admin = isOrgAdmin(me)
  const hasOrg = Boolean(me?.org)
  const canConfigureSso = admin && hasOrg

  async function load() {
    const requests: [
      Promise<Org>,
      Promise<{ items: User[] }>,
      Promise<{ items: Tariff[] }>,
      Promise<OrgSsoAdmin> | Promise<null>,
    ] = [
      api<Org>('/org'),
      api<{ items: User[] }>('/org/users'),
      api<{ items: Tariff[] }>('/org/available-tariffs'),
      admin && hasOrg ? api<OrgSsoAdmin>('/org/sso') : Promise.resolve(null),
    ]
    const [o, u, tr, ssoConfig] = await Promise.all(requests)
    setOrg(o)
    setName(o.name)
    setTtl(o.password_ttl_days)
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
    org && (name.trim() !== org.name || ttl !== org.password_ttl_days),
  )

  async function saveProfile() {
    if (!org) return
    const tasks: Promise<unknown>[] = []
    const trimmed = name.trim()
    if (trimmed && trimmed !== org.name) {
      tasks.push(api('/org', { method: 'PATCH', body: JSON.stringify({ name: trimmed }) }))
    }
    if (ttl !== org.password_ttl_days) {
      tasks.push(api('/org/settings', { method: 'PATCH', body: JSON.stringify({ password_ttl_days: ttl }) }))
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

  async function addUser() {
    try {
      await api('/org/users', { method: 'POST', body: JSON.stringify({ email, password, role }) })
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
    const r = await api<{ password: string }>(`/org/users/${user.id}/reset-password`, { method: 'POST' })
    setTempPw(r.password)
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
    <div>
      <h1>{t('org.title')}</h1>
      {org && (
        <div className="org-settings-grid">
          <div className="card stack">
            <h2 className="org-settings-heading">{t('org.profile')}</h2>
            <label>
              {t('common.name')}
              <input value={name} disabled={!admin} onChange={(e) => setName(e.target.value)} />
            </label>
            <label>
              {t('org.ttl')}
              <input type="number" min={0} value={ttl} disabled={!admin} onChange={(e) => setTtl(Number(e.target.value))} />
            </label>
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
          </div>
          <div className="card stack">
            <h2 className="org-settings-heading">{t('org.tariff')}</h2>
            <WalletLabel unlimited={org.unlimited} balance={org.balance} />
            {!admin && currentTariff && (
              <>
                <div className="row">
                  <strong className="grow">{t('org.tariff')}: {currentTariff.name}</strong>
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
              <button type="button" disabled={!canSaveTariff} onClick={() => void saveTariff()}>
                {t('common.save')}
              </button>
            )}
          </div>
        </div>
      )}
      {canConfigureSso && (
        <details className="fold org-sso-fold card">
          <summary className="org-sso-summary">
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
            sso.public_base_url_set && sso.login_url && sso.callback_url ? (
              <div className="sso-ref">
                <SsoUrlRow label={t('sso.callbackUrl')} value={sso.callback_url} />
                <SsoUrlRow label={t('sso.loginUrl')} value={sso.login_url} />
              </div>
            ) : (
              <p className="err sso-lead">{t('sso.publicBaseUrlMissing')}</p>
            )
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
      <h2>{t('org.people')}</h2>
      {tempPw && (
        <p className="ok">
          {t('org.newPassword')}: <code className="secret">{tempPw}</code>
        </p>
      )}
      {admin && (
        <div className="card stack" style={{ marginBottom: 12 }}>
          <h3>{t('org.addUser')}</h3>
          <label>
            {t('common.email')}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            {t('common.password')}
            <input type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
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
      )}
      <table>
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
                  u.role
                )}
              </td>
              <td>{u.disabled ? t('common.disable') : t('common.enable')}</td>
              {admin && (
                <td className="row">
                  {u.id !== me?.user.id && !u.disabled && (
                    <button
                      type="button"
                      onClick={() =>
                        void api('/impersonate', {
                          method: 'POST',
                          body: JSON.stringify({ user_id: u.id }),
                        }).then(() => refresh()).then(() => nav(LIBRARY_DEFAULT))
                      }
                    >
                      {t('org.impersonate')}
                    </button>
                  )}
                  <button type="button" onClick={() => void toggleDisabled(u)}>
                    {u.disabled ? t('common.enable') : t('common.disable')}
                  </button>
                  <button type="button" onClick={() => void resetPw(u)}>{t('org.resetPassword')}</button>
                  <button type="button" className="danger" onClick={() => setOffUser(u)}>{t('org.offboard')}</button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {offUser && (
        <div className="modal-back" onClick={() => setOffUser(null)}>
          <div className="card modal stack" onClick={(e) => e.stopPropagation()}>
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
            <div className="row">
              <button className="danger" type="button" onClick={() => void offboard()}>{t('common.confirm')}</button>
              <button type="button" onClick={() => setOffUser(null)}>{t('common.cancel')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
