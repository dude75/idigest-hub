import { useTranslation } from 'react-i18next'
import type { Org, OrgLedger, OrgLedgerEntry } from '../types'
import { formatDecimal, formatInteger, fmtDate, fmtMediaTime, WalletLabel } from '../util'
import { StatCard, StatGrid } from './StatCard'
import { StatsFiltersPanel } from './StatsFiltersPanel'
import { StatsPeriodCaption } from './StatsPeriodCaption'

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
  if (n > 0) return 'ledger-amt pos'
  if (n < 0) return 'ledger-amt neg'
  return 'ledger-amt zero'
}

function entryBadge(entry: OrgLedgerEntry): string {
  if (entry.entry_type === 'charge') return 'badge ledger-badge charge'
  const n = Number(entry.amount)
  if (n > 0) return 'badge ledger-badge topup'
  return 'badge ledger-badge adjust'
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
    <div className="modal-back org-ledger-back" onClick={onClose}>
      <div className="org-ledger-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <header className="org-ledger-head">
          <div className="org-ledger-title">
            <h2>{org.name}</h2>
            <div className="org-ledger-meta">
              <span className="badge">{org.tariff.name}</span>
              {org.unlimited && <span className="badge out">{t('instance.unlimited')}</span>}
              <span className="muted">
                {t('instance.users')} · {formatInteger((org.members || []).length)}
              </span>
            </div>
          </div>
          <div className="org-ledger-head-actions">
            <div className="org-ledger-balance">
              <WalletLabel unlimited={org.unlimited} balance={org.balance} />
            </div>
            <button type="button" className="icon-btn" onClick={onClose} aria-label={t('common.close')}>×</button>
          </div>
        </header>

        <section className="org-ledger-filters">
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
        </section>

        <div className="org-ledger-content">
          {!ledger ? (
            <p className="muted org-ledger-loading">{t('common.loading')}</p>
          ) : (
            <>
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

              <div className="org-ledger-body">
                <h3>{t('instance.ledger')}</h3>
                {ledger.items.length === 0 ? (
                  <p className="muted org-ledger-empty">{t('common.empty')}</p>
                ) : (
                  <div className="org-ledger-table-wrap">
                    <table className="stats-table org-ledger-table">
                      <thead>
                        <tr>
                          <th>{t('instance.ledgerDate')}</th>
                          <th>{t('instance.ledgerType')}</th>
                          <th>{t('stats.user')}</th>
                          <th>{t('stats.kind')}</th>
                          <th className="num">{t('instance.ledgerAmount')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ledger.items.map((entry) => (
                          <tr key={entry.id}>
                            <td className="ledger-date stats-day">{fmtDate(entry.created_at)}</td>
                            <td>
                              <span className={entryBadge(entry)}>{typeLabel(entry)}</span>
                              {entry.unlimited_skip && (
                                <span className="ledger-note muted">{t('instance.ledgerUnlimitedSkip')}</span>
                              )}
                            </td>
                            <td className="ledger-user">{entry.user_email || entry.actor_email || '—'}</td>
                            <td className="ledger-detail">
                              {entry.kind ? (
                                <span>{t(`task.type.${entry.kind}`)}</span>
                              ) : (
                                <span className="muted">—</span>
                              )}
                              {entry.audio_sec != null && (
                                <div className="muted">{fmtMediaTime(entry.audio_sec)}</div>
                              )}
                              {entry.summary_chars != null && entry.summary_chars > 0 && (
                                <div className="muted">
                                  {formatInteger(entry.summary_chars)} {t('stats.statChars')}
                                </div>
                              )}
                            </td>
                            <td className="num">
                              <span className={amountClass(entry.amount)}>{formatDecimal(entry.amount)}</span>
                              {entry.unlimited_skip && entry.usage_amount && (
                                <div className="muted ledger-note">{formatDecimal(entry.usage_amount)}</div>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
