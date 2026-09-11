import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { detectLedgerPreset, OrgLedgerModal } from '../../components/OrgLedgerModal'
import type { Org, OrgLedger, Tariff } from '../../types'
import { datePreset, statsRangeForDays, utcDay } from '../../util/date'
import { showError } from '../../util'

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
  const [tempPw, setTempPw] = useState<{ email: string; password: string } | null>(null)

  const orgLedgerQuery = useMemo(() => {
    const params = new URLSearchParams()
    if (orgFromDay) params.set('from', orgFromDay)
    if (orgToDay) params.set('to', orgToDay)
    if (orgUserId) params.set('user_id', orgUserId)
    if (orgKind) params.set('kind', orgKind)
    const text = params.toString()
    return text ? `?${text}` : ''
  }, [orgFromDay, orgToDay, orgUserId, orgKind])

  const orgActivePreset = useMemo(
    () => detectLedgerPreset(orgFromDay, orgToDay, utcDay),
    [orgFromDay, orgToDay],
  )

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

  return (
    <>
      {tempPw && (
        <p className="ok" style={{ marginBottom: 12 }}>
          {t('org.newPassword')} ({tempPw.email}): <code className="secret">{tempPw.password}</code>
        </p>
      )}
      <label className="row" style={{ marginBottom: 12 }}>
        <input type="checkbox" checked={showHiddenOrgs} onChange={(e) => setShowHiddenOrgs(e.target.checked)} />
        {t('library.showHidden', { count: hiddenOrgCount })}
      </label>
      <div className="org-cards">
        {orgs.length === 0 && <p className="muted">{t('common.empty')}</p>}
        {orgs.map((o) => (
          <article className="org-card" key={o.id}>
            <section className="org-tile org-tile-info">
              <h3 className="org-card-title">{o.name}</h3>
              <div className="org-card-meta">
                <span className="badge">{o.tariff.name}</span>
                {o.unlimited ? (
                  <span className="badge out">{t('wallet.unlimited')}</span>
                ) : (
                  <span className="org-balance">{o.balance}</span>
                )}
                {o.hidden && <span className="badge">{t('library.hidden')}</span>}
                <span className="muted org-member-count">
                  {t('instance.users')} · {(o.members || []).length}
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
                <div className="org-ops-field org-wallet-field">
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
                            onClick={() => void api('/impersonate', { method: 'POST', body: JSON.stringify({ user_id: u.id }) }).then(() => refresh())}
                          >
                            {t('instance.impersonate')}
                          </button>
                        )}
                        {u.role === 'org_admin' && !u.is_instance_admin && (
                          <button
                            type="button"
                            onClick={() =>
                              void api<{ password: string }>(`/orgs/${o.id}/users/${u.id}/reset-password`, { method: 'POST' })
                                .then((r) => setTempPw({ email: u.email, password: r.password }))
                                .catch(showError)
                            }
                          >
                            {t('org.resetPassword')}
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

      {orgCard && (
        <OrgLedgerModal
          org={orgCard}
          ledger={orgLedger}
          fromDay={orgFromDay}
          toDay={orgToDay}
          userId={orgUserId}
          kind={orgKind}
          activePreset={orgActivePreset}
          onClose={() => setOrgCard(null)}
          onFromDayChange={setOrgFromDay}
          onToDayChange={setOrgToDay}
          onUserIdChange={setOrgUserId}
          onKindChange={setOrgKind}
          onPreset={(days) => datePreset(days, setOrgFromDay, setOrgToDay)}
        />
      )}
    </>
  )
}
