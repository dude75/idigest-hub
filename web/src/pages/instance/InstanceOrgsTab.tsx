import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { AdminFormCard, AdminPage, AdminTableCard } from '../../components/AdminSection'
import {
  AdminDataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  adminTableCellActions,
  adminTableCellBadges,
  adminTableHeadActions,
} from '../../components/app/AdminDataTable'
import { AdminFormActions, AppSubmitButton, HubBadge } from '../../components/app/AdminUi'
import { AppHoverHint } from '../../components/app/AppHoverHint'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Modal } from '../../components/Modal'
import { UserStatusBadges } from '../../components/UserAgreementBadge'
import { OrgLedgerModal } from '../../components/OrgLedgerModal'
import { StatCard, StatGrid } from '../../components/StatCard'
import type { Org, OrgLedger, Tariff, User } from '../../types'
import { defaultFilterRange } from '../../util/date'
import { randomPassword } from '../../util/password'
import { formatInteger, showError, WalletLabel } from '../../util'
import { canAdminResetMemberMfa } from '../../mfa'
import { emptyOrg } from './constants'
import { Button } from '@/components/ui/button'
import { AppSelect } from '../../components/app/AppSelect'
import { AppCheckboxRow, AppInputField, AppSelectField } from '../../components/app/AppFormControls'
import { AppField } from '../../components/app/AppField'
import { AppUrlCopyRow } from '../../components/app/AppUrlCopyRow'
import { Input } from '@/components/ui/input'

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
  const [orgFromDay, setOrgFromDay] = useState(() => defaultFilterRange().from)
  const [orgToDay, setOrgToDay] = useState(() => defaultFilterRange().to)
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
  const [orgFormOpen, setOrgFormOpen] = useState(false)
  const orgFormRef = useRef<HTMLDivElement>(null)

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
    const range = defaultFilterRange()
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

  const orgCreateReady = useMemo(() => {
    const email = orgForm.admin_email.trim()
    return orgForm.name.trim().length > 0 && email.includes('@')
  }, [orgForm])

  function scrollToOrgForm() {
    requestAnimationFrame(() => orgFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  function openCreateOrg() {
    setOrgForm(ensureOrgPassword(emptyOrg))
    setOrgFormOpen(true)
    scrollToOrgForm()
  }

  function cancelCreateOrg() {
    setOrgForm(emptyOrg)
    setOrgFormOpen(false)
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
      setOrgFormOpen(false)
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

      {orgFormOpen ? (
        <div ref={orgFormRef}>
          <AdminFormCard title={t('instance.orgCreate')}>
          <AppInputField
            label={t('common.name')}
            htmlFor="instance-org-create-name"
            value={orgForm.name}
            onChange={(e) => setOrgForm({ ...orgForm, name: e.target.value })}
          />
          <AppSelectField
            label={t('org.tariff')}
            htmlFor="instance-org-create-tariff"
            value={orgForm.tariff_id || activeTariffs[0]?.id || ''}
            onValueChange={(tariff_id) => setOrgForm({ ...orgForm, tariff_id })}
            options={activeTariffs.map((tr) => ({ value: tr.id, label: tr.name }))}
          />
          <AppInputField
            label={t('instance.orgAdminEmail')}
            htmlFor="instance-org-create-email"
            type="email"
            value={orgForm.admin_email}
            onChange={(e) => setOrgForm({ ...orgForm, admin_email: e.target.value })}
          />
          <AppField label={t('instance.orgAdminPassword')} htmlFor="instance-org-create-password">
            <div className="public-link-actions-row">
              <AppUrlCopyRow
                value={orgForm.admin_password}
                id="instance-org-create-password"
              />
              <Button
                type="button"
                variant="outline"
                className="public-link-revoke"
                onClick={() => setOrgForm({ ...orgForm, admin_password: randomPassword() })}
              >
                {t('instance.orgGeneratePassword')}
              </Button>
            </div>
          </AppField>
          <AdminFormActions>
            <AppSubmitButton ready={orgCreateReady} busy={createBusy} onClick={() => void createOrg()}>
              {t('common.create')}
            </AppSubmitButton>
            <Button type="button" variant="outline" disabled={createBusy} onClick={cancelCreateOrg}>
              {t('common.cancel')}
            </Button>
          </AdminFormActions>
          </AdminFormCard>
        </div>
      ) : null}

      <AdminTableCard
        title={t('instance.orgsTotal')}
        empty={t('common.empty')}
        isEmpty={orgs.length === 0}
        tableLayout={orgs.length > 0}
        actions={
          <div className="flex flex-wrap items-center justify-end gap-3">
            <AppCheckboxRow
              id="instance-orgs-show-hidden"
              className="admin-toolbar-check"
              label={t('library.showHidden', { count: hiddenOrgCount })}
              checked={showHiddenOrgs}
              onCheckedChange={setShowHiddenOrgs}
            />
            <Button type="button" size="sm" onClick={openCreateOrg}>
              {t('instance.orgCreate')}
            </Button>
          </div>
        }
      >
        {orgs.length > 0 ? (
          <div className="org-cards org-cards-embedded">
        {orgs.map((o) => (
          <article className="org-card" key={o.id}>
            <section className="org-tile org-tile-info">
              <h3 className="org-card-title">{o.name}</h3>
              <div className="org-card-meta">
                <HubBadge tone="muted">{o.tariff.name}</HubBadge>
                <WalletLabel unlimited={o.unlimited} balance={o.balance} />
                {o.hidden ? <HubBadge tone="pending">{t('library.hidden')}</HubBadge> : null}
                <span className="muted org-member-count">
                  {t('instance.users')} · {formatInteger((o.members || []).length)}
                </span>
              </div>
              <div className="org-card-foot">
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto px-0 text-sm text-primary"
                  onClick={() => openOrgCard(o)}
                >
                  {t('instance.ledger')} →
                </Button>
                <AppHoverHint content={t('instance.orgHideHint')}>
                  <Button
                    type="button"
                    variant="link"
                    size="sm"
                    className="h-auto px-0 text-sm text-muted-foreground"
                    onClick={() => void toggleOrgHidden(o)}
                  >
                    {o.hidden ? t('common.unhide') : t('common.hide')}
                  </Button>
                </AppHoverHint>
                <AppHoverHint content={t('instance.orgDeleteHint')}>
                  <Button
                    type="button"
                    variant="link"
                    size="sm"
                    className="h-auto px-0 text-sm text-destructive"
                    onClick={() => openDeleteOrg(o)}
                  >
                    {t('instance.orgDelete')}
                  </Button>
                </AppHoverHint>
              </div>
            </section>
            <section className="org-tile org-tile-ops">
              <div className="org-ops-toolbar">
                <div className="org-ops-field">
                  <AppSelectField
                    label={t('org.tariff')}
                    htmlFor={`org-tariff-${o.id}`}
                    value={o.tariff.id}
                    onValueChange={(tariff_id) =>
                      void api(`/orgs/${o.id}/tariff`, { method: 'PATCH', body: JSON.stringify({ tariff_id }) }).then(load)
                    }
                    options={tariffs.map((tr) => ({ value: tr.id, label: tr.name }))}
                  />
                </div>
                <div className="org-ops-field">
                  <AppField label={t('instance.walletDelta')} htmlFor={`org-wallet-${o.id}`}>
                    <div className="org-wallet-inline">
                      <Input
                        id={`org-wallet-${o.id}`}
                        placeholder="+100"
                        value={deltas[o.id] || ''}
                        onChange={(e) => setDeltas((d) => ({ ...d, [o.id]: e.target.value }))}
                      />
                      <Button type="button" onClick={() => void api(`/orgs/${o.id}/wallet`, { method: 'POST', body: JSON.stringify({ delta: deltas[o.id] }) }).then(load)}
                      >
                        {t('instance.apply')}
                      </Button>
                    </div>
                  </AppField>
                </div>
              </div>
              {(o.members || []).length > 0 && (
                <details className="org-users">
                  <summary>{t('instance.users')}</summary>
                  <div className="org-users-table-wrap">
                    <AdminDataTable className="org-users-table">
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('common.email')}</TableHead>
                          <TableHead>{t('common.role')}</TableHead>
                          <TableHead>{t('common.status')}</TableHead>
                          <TableHead className={adminTableHeadActions}>{t('instance.impersonate')}</TableHead>
                          <TableHead className={adminTableHeadActions}>{t('org.resetPassword')}</TableHead>
                          <TableHead className={adminTableHeadActions}>{t('org.resetMfa')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(o.members || []).map((u) => (
                          <TableRow key={u.id}>
                            <TableCell className="org-users-email max-w-[14rem] truncate" title={u.email}>
                              {u.email}
                            </TableCell>
                            <TableCell>
                              {!u.is_instance_admin ? (
                                <AppSelect
                                  id={`org-user-role-${u.id}`}
                                  className="h-8 min-w-[8rem]"
                                  value={u.role ?? 'org_member'}
                                  onValueChange={(role) =>
                                    void api(`/orgs/${o.id}/users/${u.id}`, {
                                      method: 'PATCH',
                                      body: JSON.stringify({ role }),
                                    })
                                      .then(load)
                                      .catch(showError)
                                  }
                                  options={[
                                    { value: 'org_admin', label: t('org.roleAdmin') },
                                    { value: 'org_member', label: t('org.roleMember') },
                                  ]}
                                />
                              ) : (
                                <HubBadge tone="muted">{u.role}</HubBadge>
                              )}
                            </TableCell>
                            <TableCell className={adminTableCellBadges}>
                              <UserStatusBadges user={u} />
                            </TableCell>
                            <TableCell className={adminTableCellActions}>
                              {!u.is_instance_admin ? (
                                <Button type="button" size="sm" variant="outline" onClick={() =>
                                    void api('/impersonate', { method: 'POST', body: JSON.stringify({ user_id: u.id }) })
                                      .then(() => refresh())
                                      .catch(showError)
                                  }
                                >
                                  {t('instance.impersonate')}
                                </Button>
                              ) : null}
                            </TableCell>
                            <TableCell className={adminTableCellActions}>
                              {u.role === 'org_admin' && !u.is_instance_admin ? (
                                <Button type="button" size="sm" variant="outline" onClick={() =>
                                    void api<{ password: string }>(`/orgs/${o.id}/users/${u.id}/reset-password`, { method: 'POST' })
                                      .then((r) => setTempPw({ email: u.email, password: r.password, kind: 'reset' }))
                                      .catch(showError)
                                  }
                                >
                                  {t('org.resetPassword')}
                                </Button>
                              ) : null}
                            </TableCell>
                            <TableCell className={adminTableCellActions}>
                              {canAdminResetMemberMfa(u) ? (
                                <Button type="button" size="sm" variant="outline" onClick={() => setMfaResetTarget({ orgId: o.id, user: u })}
                                >
                                  {t('org.resetMfa')}
                                </Button>
                              ) : null}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </AdminDataTable>
                  </div>
                </details>
              )}
            </section>
          </article>
        ))}
          </div>
        ) : null}
      </AdminTableCard>

      {tempPw ? (
        <Modal
          onClose={() => setTempPw(null)}
          title={tempPw.kind === 'reset' ? t('org.resetPassword') : t('instance.orgCreate')}
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
      {deleteTarget ? (
        <Modal
          onClose={() => {
            if (deleteBusy) return
            setDeleteTarget(null)
            setDeleteConfirmName('')
          }}
          closeOnBackdrop={!deleteBusy}
          title={t('instance.orgDeleteTitle')}
          description={t('instance.orgDeleteHint')}
          footer={
            <>
              <Button
                type="button"
                variant="outline"
                disabled={deleteBusy}
                onClick={() => {
                  setDeleteTarget(null)
                  setDeleteConfirmName('')
                }}
              >
                {t('common.cancel')}
              </Button>
              <Button
                type="button"
                variant="destructive"
                disabled={deleteBusy || deleteConfirmName.trim() !== deleteTarget.name}
                onClick={() => void confirmDeleteOrg()}
              >
                {t('instance.orgDelete')}
              </Button>
            </>
          }
        >
          <p className="text-sm">{t('instance.orgDeleteMembersWarning', { count: (deleteTarget.members || []).length })}</p>
          <AppInputField
            label={t('instance.orgDeleteConfirmHint', { name: deleteTarget.name })}
            htmlFor="instance-org-delete-confirm"
            value={deleteConfirmName}
            autoComplete="off"
            autoFocus
            disabled={deleteBusy}
            onChange={(e) => setDeleteConfirmName(e.target.value)}
          />
        </Modal>
      ) : null}
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
                return load()
              })
              .catch((e) => {
                showError(e)
                return load()
              })
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
