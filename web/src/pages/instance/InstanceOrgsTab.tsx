import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { AdminPage } from '../../components/AdminSection'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Modal } from '../../components/Modal'
import { OrgLedgerModal } from '../../components/OrgLedgerModal'
import { StatCard, StatGrid } from '../../components/StatCard'
import type { Org, OrgLedger, Tariff, User } from '../../types'
import { statsRangeForDays } from '../../util/date'
import { randomPassword } from '../../util/password'
import { formatInteger, showError, WalletLabel } from '../../util'
import { emptyOrg } from './constants'

export function InstanceOrgsTab() {
  const { t } = useTranslation()
  const { refresh } = useAuth()
  const [orgs, setOrgs] = useState<Org[]>([])
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [deltas, setDeltas] = useState<Record<string, string>>({})
  const [showHiddenOrgs, setShowHiddenOrgs] = useState(false)
  const [hiddenOrgCount, setHiddenOrgCount] = useState(0)
  const [orgCard, setOrgCard] = useState<Org | null>(null)
  const [orgLedger, setOrgLedger] = useState<OrgLedger | null>(null)
  const [orgFromDay, setOrgFromDay] = useState(() => statsRangeForDays(7).from)
  const [orgToDay, setOrgToDay] = useState(() => statsRangeForDays(7).to)
  const [orgUserId, setOrgUserId] = useState('')
  const [orgKind, setOrgKind] = useState('')
  const [tempPw, setTempPw] = useState<{ email: string; password: string; kind: 'create' | 'reset' } | null>(null)
  const [mfaResetTarget, setMfaResetTarget] = useState<{ orgId: string; user: User } | null>(null)
  const [mfaResetBusy, setMfaResetBusy] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Org | null>(null)
  const [deleteConfirmName, setDeleteConfirmName] = useState('')
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [orgForm, setOrgForm] = useState(emptyOrg)
  const [createBusy, setCreateBusy] = useState(false)
  const [copiedPassword, setCopiedPassword] = useState(false)
  const [copiedModalPassword, setCopiedModalPassword] = useState(false)

  const activeTariffs = useMemo(
    () => tariffs.filter((tr) => !tr.archived),
    [tariffs],
  )

  const orgLedgerQuery = useMemo(() => {
    const params = new URLSearchParams()
    if (orgFromDay) params.set('from', orgFromDay)
    if (orgToDay) params.set('to', orgToDay)
    if (orgUserId) params.set('user_id', orgUserId)
    if (orgKind) params.set('kind', orgKind)
    const text = params.toString()
    return text ? `?${text}` : ''
  }, [orgFromDay, orgToDay, orgUserId, orgKind])

  const summary = useMemo(() => ({
    total: orgs.length,
    members: orgs.reduce((sum, o) => sum + (o.members || []).length, 0),
    hidden: orgs.filter((o) => o.hidden).length,
    unlimited: orgs.filter((o) => o.unlimited).length,
  }), [orgs])

  async function load() {
    try {
      const orgQuery = showHiddenOrgs ? '?include_hidden=true' : ''
      const [o, tr] = await Promise.all([
        api<{ items: Org[]; hidden_count: number }>(`/orgs${orgQuery}`),
        api<{ items: Tariff[] }>('/tariffs'),
      ])
      setOrgs(o.items)
      setHiddenOrgCount(o.hidden_count ?? 0)
      setTariffs(tr.items)
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    void load()
  }, [showHiddenOrgs])

  useEffect(() => {
    if (!orgCard) return
    api<OrgLedger>(`/orgs/${orgCard.id}/ledger${orgLedgerQuery}`)
      .then(setOrgLedger)
      .catch(showError)
  }, [orgCard, orgLedgerQuery])

  function openOrgCard(org: Org) {
    const range = statsRangeForDays(7)
    setOrgFromDay(range.from)
    setOrgToDay(range.to)
    setOrgUserId('')
    setOrgKind('')
    setOrgLedger(null)
    setOrgCard(org)
  }

  async function toggleOrgHidden(org: Org) {
    try {
      await api(`/orgs/${org.id}/${org.hidden ? 'unhide' : 'hide'}`, { method: 'POST' })
      await load()
    } catch (e) {
      showError(e)
    }
  }

  function ensureOrgPassword(form = orgForm) {
    if (form.admin_password) return form
    return { ...form, admin_password: randomPassword() }
  }

  async function copyPassword(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedPassword(true)
      window.setTimeout(() => setCopiedPassword(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  async function copyModalPassword() {
    if (!tempPw) return
    try {
      await navigator.clipboard.writeText(tempPw.password)
      setCopiedModalPassword(true)
      window.setTimeout(() => setCopiedModalPassword(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  function openDeleteOrg(org: Org) {
    if (orgCard?.id === org.id) setOrgCard(null)
    setDeleteConfirmName('')
    setDeleteTarget(org)
  }

  async function confirmDeleteOrg() {
    if (!deleteTarget) return
    setDeleteBusy(true)
    try {
      await api(`/orgs/${deleteTarget.id}/delete`, {
        method: 'POST',
        body: JSON.stringify({ confirm_name: deleteConfirmName.trim() }),
      })
      setDeleteTarget(null)
      setDeleteConfirmName('')
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setDeleteBusy(false)
    }
  }

  async function createOrg() {
    const payload = ensureOrgPassword()
    setCreateBusy(true)
    try {
      await api('/orgs', {
        method: 'POST',
        body: JSON.stringify({
          ...payload,
          tariff_id: payload.tariff_id || activeTariffs[0]?.id,
        }),
      })
      setTempPw({ email: payload.admin_email, password: payload.admin_password, kind: 'create' })
      setOrgForm(emptyOrg)
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setCreateBusy(false)
    }
  }

  return (
    <AdminPage>
      <StatGrid>
        <StatCard label={t('instance.orgsTotal')} value={formatInteger(summary.total)} tone="ops" />
        <StatCard label={t('instance.users')} value={formatInteger(summary.members)} tone="transcribe" />
        <StatCard label={t('instance.orgsUnlimited')} value={formatInteger(summary.unlimited)} tone="summarize" />
        <StatCard
          label={t('instance.orgsHidden')}
          value={formatInteger(showHiddenOrgs ? summary.hidden : hiddenOrgCount)}
          tone="amount"
        />
      </StatGrid>

      <details
        className="fold org-fold org-create-fold card"
        onToggle={(e) => {
          if (e.currentTarget.open) setOrgForm((form) => ensureOrgPassword(form))
        }}
      >
        <summary className="org-fold-summary">
          <span>{t('instance.orgCreate')}</span>
        </summary>
        <div className="stack fold-body">
          <label>
            {t('common.name')}
            <input value={orgForm.name} onChange={(e) => setOrgForm({ ...orgForm, name: e.target.value })} />
          </label>
          <label>
            {t('org.tariff')}
            <select
              value={orgForm.tariff_id || activeTariffs[0]?.id || ''}
              onChange={(e) => setOrgForm({ ...orgForm, tariff_id: e.target.value })}
            >
              {activeTariffs.map((tr) => (
                <option key={tr.id} value={tr.id}>{tr.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t('instance.orgAdminEmail')}
            <input
              type="email"
              value={orgForm.admin_email}
              onChange={(e) => setOrgForm({ ...orgForm, admin_email: e.target.value })}
            />
          </label>
          <label>
            {t('instance.orgAdminPassword')}
            <div className="public-link-actions-row">
              <div className="public-link-url-row">
                <code className="public-link-url" title={orgForm.admin_password}>
                  {orgForm.admin_password || '—'}
                </code>
                <button
                  type="button"
                  className="public-link-copy"
                  disabled={!orgForm.admin_password}
                  onClick={() => void copyPassword(orgForm.admin_password)}
                >
                  {copiedPassword ? t('profile.copied') : t('common.copy')}
                </button>
              </div>
              <button
                type="button"
                className="public-link-revoke"
                onClick={() => setOrgForm({ ...orgForm, admin_password: randomPassword() })}
              >
                {t('instance.orgGeneratePassword')}
              </button>
            </div>
          </label>
          <button className="primary" type="button" disabled={createBusy} onClick={() => void createOrg()}>
            {t('common.create')}
          </button>
        </div>
      </details>

      <div className="card admin-toolbar">
        <label className="row admin-toolbar-check">
          <input type="checkbox" checked={showHiddenOrgs} onChange={(e) => setShowHiddenOrgs(e.target.checked)} />
          {t('library.showHidden', { count: hiddenOrgCount })}
        </label>
      </div>

      <div className="org-cards">
        {orgs.length === 0 && <p className="stats-empty">{t('common.empty')}</p>}
        {orgs.map((o) => (
          <article className="org-card" key={o.id}>
            <section className="org-tile org-tile-info">
              <h3 className="org-card-title">{o.name}</h3>
              <div className="org-card-meta">
                <span className="badge">{o.tariff.name}</span>
                <WalletLabel unlimited={o.unlimited} balance={o.balance} />
                {o.hidden && <span className="badge">{t('library.hidden')}</span>}
                <span className="muted org-member-count">
                  {t('instance.users')} · {formatInteger((o.members || []).length)}
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
                <button
                  type="button"
                  className="org-delete-btn"
                  title={t('instance.orgDeleteHint')}
                  onClick={() => openDeleteOrg(o)}
                >
                  {t('instance.orgDelete')}
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
                <div className="org-ops-field">
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
                            onClick={() =>
                              void api('/impersonate', { method: 'POST', body: JSON.stringify({ user_id: u.id }) })
                                .then(() => refresh())
                                .catch(showError)
                            }
                          >
                            {t('instance.impersonate')}
                          </button>
                        )}
                        {u.role === 'org_admin' && !u.is_instance_admin && (
                          <button
                            type="button"
                            onClick={() =>
                              void api<{ password: string }>(`/orgs/${o.id}/users/${u.id}/reset-password`, { method: 'POST' })
                                .then((r) => setTempPw({ email: u.email, password: r.password, kind: 'reset' }))
                                .catch(showError)
                            }
                          >
                            {t('org.resetPassword')}
                          </button>
                        )}
                        {u.auth_provider === 'local' && (u.mfa_configured ?? u.mfa_enabled) && !u.is_instance_admin && (
                          <button
                            type="button"
                            onClick={() => setMfaResetTarget({ orgId: o.id, user: u })}
                          >
                            {t('org.resetMfa')}
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

      {tempPw && (
        <Modal onClose={() => setTempPw(null)} panelClassName="stack">
          <h2>{tempPw.kind === 'reset' ? t('org.resetPassword') : t('instance.orgCreate')}</h2>
          <p>{t('org.newPassword')} ({tempPw.email})</p>
          <div className="public-link-actions-row">
            <div className="public-link-url-row">
              <code className="public-link-url" title={tempPw.password}>{tempPw.password}</code>
              <button
                type="button"
                className="public-link-copy"
                onClick={() => void copyModalPassword()}
              >
                {copiedModalPassword ? t('profile.copied') : t('common.copy')}
              </button>
            </div>
          </div>
          <div className="row modal-actions">
            <button type="button" onClick={() => setTempPw(null)}>{t('common.close')}</button>
          </div>
        </Modal>
      )}
      {deleteTarget && (
        <Modal
          onClose={() => {
            if (deleteBusy) return
            setDeleteTarget(null)
            setDeleteConfirmName('')
          }}
          closeOnBackdrop={!deleteBusy}
          panelClassName="stack"
        >
          <h2>{t('instance.orgDeleteTitle')}</h2>
          <p className="err">{t('instance.orgDeleteHint')}</p>
          <p>{t('instance.orgDeleteMembersWarning', { count: (deleteTarget.members || []).length })}</p>
          <label>
            {t('instance.orgDeleteConfirmHint', { name: deleteTarget.name })}
            <input
              value={deleteConfirmName}
              autoComplete="off"
              autoFocus
              disabled={deleteBusy}
              onChange={(e) => setDeleteConfirmName(e.target.value)}
            />
          </label>
          <div className="row modal-actions">
            <button
              type="button"
              className="danger"
              disabled={deleteBusy || deleteConfirmName.trim() !== deleteTarget.name}
              onClick={() => void confirmDeleteOrg()}
            >
              {t('instance.orgDelete')}
            </button>
            <button
              type="button"
              disabled={deleteBusy}
              onClick={() => {
                setDeleteTarget(null)
                setDeleteConfirmName('')
              }}
            >
              {t('common.cancel')}
            </button>
          </div>
        </Modal>
      )}
      {mfaResetTarget && (
        <ConfirmDialog
          message={t('org.resetMfaConfirm', { email: mfaResetTarget.user.email })}
          confirmLabel={t('org.resetMfa')}
          danger
          busy={mfaResetBusy}
          onConfirm={() => {
            setMfaResetBusy(true)
            void api(`/orgs/${mfaResetTarget.orgId}/users/${mfaResetTarget.user.id}/reset-mfa`, { method: 'POST' })
              .then(() => {
                setMfaResetTarget(null)
                return refresh()
              })
              .catch(showError)
              .finally(() => setMfaResetBusy(false))
          }}
          onClose={() => setMfaResetTarget(null)}
        />
      )}
      {orgCard && (
        <OrgLedgerModal
          org={orgCard}
          ledger={orgLedger}
          fromDay={orgFromDay}
          toDay={orgToDay}
          userId={orgUserId}
          kind={orgKind}
          onClose={() => setOrgCard(null)}
          onFromDayChange={setOrgFromDay}
          onToDayChange={setOrgToDay}
          onUserIdChange={setOrgUserId}
          onKindChange={setOrgKind}
        />
      )}
    </AdminPage>
  )
}
