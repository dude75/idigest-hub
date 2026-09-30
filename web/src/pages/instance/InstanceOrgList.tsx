import { Fragment, type Dispatch, type SetStateAction } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, MoreHorizontal } from 'lucide-react'
import { api } from '../../api'
import {
  AdminDataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  adminTableCellActions,
  adminTableCellBadges,
  adminTableCellNum,
  adminTableCellPrimary,
  adminTableHeadActions,
  adminTableHeadNum,
} from '../../components/app/AdminDataTable'
import { AdminMetaRow, AdminRowActions, HubBadge } from '../../components/app/AdminUi'
import { AppHoverHint } from '../../components/app/AppHoverHint'
import { AppSelect } from '../../components/app/AppSelect'
import { AppSelectField } from '../../components/app/AppFormControls'
import { AppField } from '../../components/app/AppField'
import { UserStatusBadges } from '../../components/UserAgreementBadge'
import type { Org, Tariff, User } from '../../types'
import { formatDecimal, formatInteger, showError } from '../../util'
import { canAdminResetMemberMfa } from '../../mfa'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

type InstanceOrgListProps = {
  orgs: Org[]
  tariffs: Tariff[]
  deltas: Record<string, string>
  setDeltas: Dispatch<SetStateAction<Record<string, string>>>
  expandedOrgId: string | null
  setExpandedOrgId: Dispatch<SetStateAction<string | null>>
  onReload: () => void | Promise<void>
  onRefreshAuth: () => void | Promise<void>
  onOpenLedger: (org: Org) => void
  onToggleHidden: (org: Org) => void
  onDelete: (org: Org) => void
  onTempPassword: (email: string, password: string) => void
  onMfaReset: (orgId: string, user: User) => void
}

function OrgWalletCell({ org }: { org: Org }) {
  const { t } = useTranslation()
  if (org.unlimited) {
    return <HubBadge tone="success">{t('instance.unlimited')}</HubBadge>
  }
  if (org.balance == null) return <span className="text-muted-foreground">—</span>
  return <span className="font-medium tabular-nums">{formatDecimal(org.balance)}</span>
}

function OrgMembersTable({
  org,
  onReload,
  onRefreshAuth,
  onTempPassword,
  onMfaReset,
}: {
  org: Org
  onReload: () => void | Promise<void>
  onRefreshAuth: () => void | Promise<void>
  onTempPassword: (email: string, password: string) => void
  onMfaReset: (orgId: string, user: User) => void
}) {
  const { t } = useTranslation()
  const members = org.members || []

  if (members.length === 0) {
    return <p className="instance-org-empty-members">{t('common.empty')}</p>
  }

  return (
    <AdminDataTable className="instance-org-users-table">
      <TableHeader>
        <TableRow>
          <TableHead>{t('common.email')}</TableHead>
          <TableHead>{t('common.role')}</TableHead>
          <TableHead>{t('common.status')}</TableHead>
          <TableHead className={adminTableHeadActions}>{t('common.actions')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.map((u) => (
          <TableRow key={u.id}>
            <TableCell className="max-w-[min(24rem,40vw)] truncate font-medium" title={u.email}>
              {u.email}
            </TableCell>
            <TableCell>
              {!u.is_instance_admin ? (
                <AppSelect
                  id={`org-user-role-${u.id}`}
                  className="h-8 min-w-[8.5rem]"
                  value={u.role ?? 'org_member'}
                  onValueChange={(role) =>
                    void api(`/orgs/${org.id}/users/${u.id}`, {
                      method: 'PATCH',
                      body: JSON.stringify({ role }),
                    })
                      .then(onReload)
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
              <AdminRowActions>
                {!u.is_instance_admin ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      void api('/impersonate', { method: 'POST', body: JSON.stringify({ user_id: u.id }) })
                        .then(() => onRefreshAuth())
                        .catch(showError)
                    }
                  >
                    {t('instance.impersonate')}
                  </Button>
                ) : null}
                {u.role === 'org_admin' && !u.is_instance_admin ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      void api<{ password: string }>(`/orgs/${org.id}/users/${u.id}/reset-password`, {
                        method: 'POST',
                      })
                        .then((r) => onTempPassword(u.email, r.password))
                        .catch(showError)
                    }
                  >
                    {t('org.resetPassword')}
                  </Button>
                ) : null}
                {canAdminResetMemberMfa(u) ? (
                  <Button type="button" size="sm" variant="outline" onClick={() => onMfaReset(org.id, u)}>
                    {t('org.resetMfa')}
                  </Button>
                ) : null}
              </AdminRowActions>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </AdminDataTable>
  )
}

function OrgDetailPanel({
  org,
  tariffs,
  delta,
  setDelta,
  onReload,
  onRefreshAuth,
  onOpenLedger,
  onToggleHidden,
  onDelete,
  onTempPassword,
  onMfaReset,
}: {
  org: Org
  tariffs: Tariff[]
  delta: string
  setDelta: (value: string) => void
  onReload: () => void | Promise<void>
  onRefreshAuth: () => void | Promise<void>
  onOpenLedger: (org: Org) => void
  onToggleHidden: (org: Org) => void
  onDelete: (org: Org) => void
  onTempPassword: (email: string, password: string) => void
  onMfaReset: (orgId: string, user: User) => void
}) {
  const { t } = useTranslation()
  const memberCount = (org.members || []).length

  return (
    <div className="instance-org-detail">
      <div className="instance-org-detail-toolbar">
        <div className="instance-org-field">
          <AppSelectField
            label={t('org.tariff')}
            htmlFor={`org-tariff-${org.id}`}
            value={org.tariff.id}
            onValueChange={(tariff_id) =>
              void api(`/orgs/${org.id}/tariff`, { method: 'PATCH', body: JSON.stringify({ tariff_id }) }).then(onReload)
            }
            options={tariffs.map((tr) => ({ value: tr.id, label: tr.name }))}
          />
        </div>
        <div className="instance-org-field instance-org-field-wallet">
          <AppField label={t('instance.walletDelta')} htmlFor={`org-wallet-${org.id}`}>
            <div className="instance-org-wallet-row">
              <Input
                id={`org-wallet-${org.id}`}
                placeholder="+100"
                value={delta}
                onChange={(e) => setDelta(e.target.value)}
              />
              <Button
                type="button"
                size="sm"
                onClick={() =>
                  void api(`/orgs/${org.id}/wallet`, {
                    method: 'POST',
                    body: JSON.stringify({ delta }),
                  }).then(onReload)
                }
              >
                {t('instance.apply')}
              </Button>
            </div>
          </AppField>
        </div>
        <div className="instance-org-detail-actions">
          <Button type="button" size="sm" variant="outline" onClick={() => onOpenLedger(org)}>
            {t('instance.openLedger')}
          </Button>
          <AppHoverHint content={t('instance.orgHideHint')}>
            <Button type="button" size="sm" variant="outline" onClick={() => onToggleHidden(org)}>
              {org.hidden ? t('common.unhide') : t('common.hide')}
            </Button>
          </AppHoverHint>
          <AppHoverHint content={t('instance.orgDeleteHint')}>
            <Button type="button" size="sm" variant="destructive" onClick={() => onDelete(org)}>
              {t('instance.orgDelete')}
            </Button>
          </AppHoverHint>
        </div>
      </div>
      <div className="instance-org-detail-users">
        <div className="instance-org-detail-users-head">
          <h4 className="instance-org-detail-users-title">
            {t('instance.users')}
            <span className="text-muted-foreground font-normal"> · {formatInteger(memberCount)}</span>
          </h4>
        </div>
        <OrgMembersTable
          org={org}
          onReload={onReload}
          onRefreshAuth={onRefreshAuth}
          onTempPassword={onTempPassword}
          onMfaReset={onMfaReset}
        />
      </div>
    </div>
  )
}

export function InstanceOrgList({
  orgs,
  tariffs,
  deltas,
  setDeltas,
  expandedOrgId,
  setExpandedOrgId,
  onReload,
  onRefreshAuth,
  onOpenLedger,
  onToggleHidden,
  onDelete,
  onTempPassword,
  onMfaReset,
}: InstanceOrgListProps) {
  const { t } = useTranslation()

  function toggleExpanded(orgId: string) {
    setExpandedOrgId((current) => (current === orgId ? null : orgId))
  }

  return (
    <AdminDataTable className="instance-org-table">
      <TableHeader>
        <TableRow>
          <TableHead className="w-[2.5rem]" aria-hidden />
          <TableHead>{t('common.name')}</TableHead>
          <TableHead>{t('org.tariff')}</TableHead>
          <TableHead>{t('wallet.balance')}</TableHead>
          <TableHead className={adminTableHeadNum}>{t('instance.users')}</TableHead>
          <TableHead className={adminTableHeadActions}>{t('common.actions')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {orgs.map((org) => {
          const expanded = expandedOrgId === org.id
          return (
            <Fragment key={org.id}>
              <TableRow data-state={expanded ? 'selected' : undefined} className="instance-org-row">
                <TableCell className="align-middle">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="instance-org-expand"
                    aria-expanded={expanded}
                    aria-label={expanded ? t('transcript.collapse') : t('transcript.expand')}
                    onClick={() => toggleExpanded(org.id)}
                  >
                    <ChevronDown className={cn('size-4 transition-transform', expanded && 'rotate-180')} />
                  </Button>
                </TableCell>
                <TableCell className={adminTableCellPrimary}>
                  <span className="block max-w-[min(14rem,28vw)] truncate" title={org.name}>
                    {org.name}
                  </span>
                  {org.hidden ? (
                    <AdminMetaRow className="mt-1">
                      <HubBadge tone="pending">{t('library.hidden')}</HubBadge>
                    </AdminMetaRow>
                  ) : null}
                </TableCell>
                <TableCell>
                  <HubBadge tone="muted">{org.tariff.name}</HubBadge>
                </TableCell>
                <TableCell>
                  <OrgWalletCell org={org} />
                </TableCell>
                <TableCell className={adminTableCellNum}>{formatInteger((org.members || []).length)}</TableCell>
                <TableCell className={adminTableCellActions}>
                  <AdminRowActions>
                    <Button type="button" size="sm" variant="outline" onClick={() => onOpenLedger(org)}>
                      {t('instance.openLedger')}
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button type="button" size="icon-sm" variant="outline" aria-label={t('common.actions')}>
                            <MoreHorizontal className="size-4" />
                          </Button>
                        }
                      />
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => toggleExpanded(org.id)}>
                          {expanded ? t('transcript.collapse') : t('transcript.expand')}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => onToggleHidden(org)}>
                          {org.hidden ? t('common.unhide') : t('common.hide')}
                        </DropdownMenuItem>
                        <DropdownMenuItem variant="destructive" onClick={() => onDelete(org)}>
                          {t('instance.orgDelete')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </AdminRowActions>
                </TableCell>
              </TableRow>
              {expanded ? (
                <TableRow className="instance-org-row-detail hover:bg-transparent">
                  <TableCell colSpan={6} className="p-0">
                    <OrgDetailPanel
                      org={org}
                      tariffs={tariffs}
                      delta={deltas[org.id] || ''}
                      setDelta={(value) => setDeltas((d) => ({ ...d, [org.id]: value }))}
                      onReload={onReload}
                      onRefreshAuth={onRefreshAuth}
                      onOpenLedger={onOpenLedger}
                      onToggleHidden={onToggleHidden}
                      onDelete={onDelete}
                      onTempPassword={onTempPassword}
                      onMfaReset={onMfaReset}
                    />
                  </TableCell>
                </TableRow>
              ) : null}
            </Fragment>
          )
        })}
      </TableBody>
    </AdminDataTable>
  )
}
