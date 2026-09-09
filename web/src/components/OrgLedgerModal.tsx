import { useTranslation } from 'react-i18next'
import type { Org, OrgLedger, OrgLedgerEntry } from '../types'
import { formatAudioTime, fmtDate, WalletLabel } from '../util'

type Preset = '7' | '30' | 'month' | 'all'

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
  onPreset: (days: number | 'month' | 'all') => void
  activePreset: Preset | null
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
  onPreset,
  activePreset,
}: Props) {
  const { t } = useTranslation()

  function typeLabel(entry: OrgLedgerEntry): string {
    if (entry.entry_type === 'charge') return t('instance.ledgerCharge')
    const amount = Number(entry.amount)
    if (amount > 0) return t('instance.ledgerTopup')
    return t('instance.ledgerWalletAdjust')
  }

  const presets: { id: Preset; label: string; run: () => void }[] = [
    { id: '7', label: t('stats.days7'), run: () => onPreset(7) },
    { id: '30', label: t('stats.days30'), run: () => onPreset(30) },
    { id: 'month', label: t('stats.month'), run: () => onPreset('month') },
    { id: 'all', label: t('stats.allTime'), run: () => onPreset('all') },
  ]

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
                {t('instance.users')} · {(org.members || []).length}
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
          <div className="preset-bar">
            {presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className={activePreset === preset.id ? 'active' : ''}
                onClick={preset.run}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <div className="org-ledger-filter-fields row wrap">
            <label>{t('stats.from')}<input type="date" value={fromDay} onChange={(e) => onFromDayChange(e.target.value)} /></label>
            <label>{t('stats.to')}<input type="date" value={toDay} onChange={(e) => onToDayChange(e.target.value)} /></label>
            <label>
              {t('stats.user')}
              <select value={userId} onChange={(e) => onUserIdChange(e.target.value)}>
                <option value="">{t('common.all')}</option>
                {(org.members || []).map((u) => (
                  <option key={u.id} value={u.id}>{u.email}</option>
                ))}
              </select>
            </label>
            <label>
              {t('stats.kind')}
              <select value={kind} onChange={(e) => onKindChange(e.target.value)}>
                <option value="">{t('common.all')}</option>
                <option value="transcribe">{t('task.type.transcribe')}</option>
                <option value="summarize">{t('task.type.summarize')}</option>
              </select>
            </label>
          </div>
        </section>

        <div className="org-ledger-content">
        {!ledger ? (
          <p className="muted org-ledger-loading">{t('common.loading')}</p>
        ) : (
          <>
            <div className="org-ledger-summary">
              <div className="ledger-stat spent">
                <div className="ledger-stat-label">{t('instance.ledgerTotalSpent')}</div>
                <div className="ledger-stat-value">{ledger.total_spent}</div>
              </div>
              <div className="ledger-stat topup">
                <div className="ledger-stat-label">{t('instance.ledgerTotalTopup')}</div>
                <div className="ledger-stat-value">{ledger.total_topup}</div>
              </div>
              <div className="ledger-stat net">
                <div className="ledger-stat-label">{t('instance.ledgerNet')}</div>
                <div className={`ledger-stat-value ${amountClass(ledger.net)}`}>{ledger.net}</div>
              </div>
            </div>

            <div className="org-ledger-body">
              <h3>{t('instance.ledger')}</h3>
              {ledger.items.length === 0 ? (
                <p className="muted org-ledger-empty">{t('common.empty')}</p>
              ) : (
                <div className="org-ledger-table-wrap">
                  <table className="org-ledger-table">
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
                          <td className="ledger-date">{fmtDate(entry.created_at)}</td>
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
                              <div className="muted">{formatAudioTime(entry.audio_sec, t)}</div>
                            )}
                            {entry.summary_chars != null && entry.summary_chars > 0 && (
                              <div className="muted">{entry.summary_chars} {t('stats.summaryChars')}</div>
                            )}
                          </td>
                          <td className="num">
                            <span className={amountClass(entry.amount)}>{entry.amount}</span>
                            {entry.unlimited_skip && entry.usage_amount && (
                              <div className="muted ledger-note">{entry.usage_amount}</div>
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

export function detectLedgerPreset(fromDay: string, toDay: string, utcDay: (d: Date) => string): Preset | null {
  if (!fromDay && !toDay) return 'all'
  const today = utcDay(new Date())
  if (toDay !== today) return null
  const to = new Date()
  const monthStart = utcDay(new Date(Date.UTC(to.getUTCFullYear(), to.getUTCMonth(), 1)))
  if (fromDay === monthStart) return 'month'
  const from7 = utcDay(new Date(to.getTime() - 6 * 86400000))
  if (fromDay === from7) return '7'
  const from30 = utcDay(new Date(to.getTime() - 29 * 86400000))
  if (fromDay === from30) return '30'
  return null
}
