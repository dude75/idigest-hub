import { useTranslation } from 'react-i18next'
import { Modal } from './Modal'
import type { Org, OrgLedger, OrgLedgerEntry } from '../types'
import { formatDecimal, formatInteger, fmtDate, fmtMediaTime, WalletLabel } from '../util'
import { StatCard, StatGrid } from './StatCard'
import { StatsFiltersPanel } from './StatsFiltersPanel'
import { StatsPeriodCaption } from './StatsPeriodCaption'
import {
  AdminDataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  adminTableCellMuted,
  adminTableCellNum,
  adminTableHeadNum,
} from './app/AdminDataTable'
import { AdminMetaRow, HubBadge } from './app/AdminUi'

type Props = {
  org: Org
  ledger: OrgLedger | null
  fromDay: string
  toDay: string
  userId: string
  kind: string
  onClose: () => void
  onFromDayChange: (value: string) => void
  onToDayChange: (value: string) => void
  onUserIdChange: (value: string) => void
  onKindChange: (value: string) => void
}

function amountClass(value: string): string {
  const n = Number(value)
  if (n > 0) return 'text-emerald-700 dark:text-emerald-400'
  if (n < 0) return 'text-destructive'
  return 'text-muted-foreground'
}

function entryTone(entry: OrgLedgerEntry): 'primary' | 'success' | 'muted' {
  if (entry.entry_type === 'charge') return 'primary'
  const n = Number(entry.amount)
  if (n > 0) return 'success'
  return 'muted'
}

export function OrgLedgerModal({
  org,
  ledger,
  fromDay,
  toDay,
  userId,
  kind,
  onClose,
  onFromDayChange,
  onToDayChange,
  onUserIdChange,
  onKindChange,
}: Props) {
  const { t } = useTranslation()

  function typeLabel(entry: OrgLedgerEntry): string {
    if (entry.entry_type === 'charge') return t('instance.ledgerCharge')
    const amount = Number(entry.amount)
    if (amount > 0) return t('instance.ledgerTopup')
    return t('instance.ledgerWalletAdjust')
  }

  return (
    <Modal
      wide
      onClose={onClose}
      title={org.name}
      panelClassName="flex max-h-[min(92vh,920px)] flex-col gap-4 overflow-hidden sm:max-w-5xl"
      description={
        <AdminMetaRow className="pt-1">
          <HubBadge tone="muted">{org.tariff.name}</HubBadge>
          {org.unlimited ? <HubBadge tone="success">{t('instance.unlimited')}</HubBadge> : null}
          <span className="text-sm text-muted-foreground">
            {t('instance.users')} · {formatInteger((org.members || []).length)}
          </span>
          <WalletLabel unlimited={org.unlimited} balance={org.balance} />
        </AdminMetaRow>
      }
    >
      <StatsFiltersPanel
        embedded
        fromDay={fromDay}
        toDay={toDay}
        onFromChange={onFromDayChange}
        onToChange={onToDayChange}
        userId={userId}
        onUserIdChange={onUserIdChange}
        users={org.members || []}
        kind={kind}
        onKindChange={onKindChange}
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!ledger ? (
          <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
        ) : (
          <div className="flex flex-col gap-4">
            <StatGrid caption={<StatsPeriodCaption fromDay={fromDay} toDay={toDay} />}>
              <StatCard
                label={t('stats.statSpent')}
                title={t('instance.ledgerTotalSpent')}
                value={formatDecimal(ledger.total_spent)}
                tone="amount"
              />
              <StatCard
                label={t('instance.ledgerTopupShort')}
                title={t('instance.ledgerTotalTopup')}
                value={formatDecimal(ledger.total_topup)}
                tone="audio"
              />
              <StatCard
                label={t('instance.ledgerNetShort')}
                title={t('instance.ledgerNet')}
                value={formatDecimal(ledger.net)}
                tone="chars"
                valueClassName={amountClass(ledger.net)}
              />
            </StatGrid>

            <div>
              <h3 className="mb-3 text-sm font-medium">{t('instance.ledger')}</h3>
              {ledger.items.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('common.empty')}</p>
              ) : (
                <AdminDataTable>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('instance.ledgerDate')}</TableHead>
                      <TableHead>{t('instance.ledgerType')}</TableHead>
                      <TableHead>{t('stats.user')}</TableHead>
                      <TableHead>{t('stats.kind')}</TableHead>
                      <TableHead className={adminTableHeadNum}>{t('instance.ledgerAmount')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {ledger.items.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell className={adminTableCellMuted}>{fmtDate(entry.created_at)}</TableCell>
                        <TableCell className="whitespace-normal">
                          <HubBadge tone={entryTone(entry)}>{typeLabel(entry)}</HubBadge>
                          {entry.unlimited_skip ? (
                            <span className="mt-1 block text-xs text-muted-foreground">
                              {t('instance.ledgerUnlimitedSkip')}
                            </span>
                          ) : null}
                        </TableCell>
                        <TableCell>{entry.user_email || entry.actor_email || '—'}</TableCell>
                        <TableCell className={adminTableCellMuted}>
                          {entry.kind ? (
                            <span>{t(`task.type.${entry.kind}`)}</span>
                          ) : (
                            '—'
                          )}
                          {entry.audio_sec != null ? (
                            <div className="text-xs">{fmtMediaTime(entry.audio_sec)}</div>
                          ) : null}
                          {entry.summary_chars != null && entry.summary_chars > 0 ? (
                            <div className="text-xs">
                              {formatInteger(entry.summary_chars)} {t('stats.statChars')}
                            </div>
                          ) : null}
                        </TableCell>
                        <TableCell className={adminTableCellNum}>
                          <span className={amountClass(entry.amount)}>{formatDecimal(entry.amount)}</span>
                          {entry.unlimited_skip && entry.usage_amount ? (
                            <div className="text-xs text-muted-foreground">{formatDecimal(entry.usage_amount)}</div>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </AdminDataTable>
              )}
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
