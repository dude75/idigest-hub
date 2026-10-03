import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { Modal } from '../../components/Modal'
import type { Tariff, TariffDeleteImpact, TariffRemediationPayload } from '../../types'
import { showError, truncateLabel } from '../../util'
import { Button } from '@/components/ui/button'
import { AppCheckboxRow, AppSelectField } from '../../components/app/AppFormControls'

type Props = {
  tariff: Tariff
  onClose: () => void
  onConfirm: (opts?: { remediation?: TariffRemediationPayload }) => void | Promise<void>
}

export function TariffImpactModal({ tariff, onClose, onConfirm }: Props) {
  const { t } = useTranslation()
  const [impact, setImpact] = useState<TariffDeleteImpact | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [applyRemediation, setApplyRemediation] = useState(true)
  const [selectedTariffId, setSelectedTariffId] = useState('')

  const suggestedId = impact?.suggested_replacement?.id ?? ''
  const selectedTariff = useMemo(() => {
    const items = impact?.available_tariffs ?? []
    if (!items.length) return null
    return items.find((item) => item.id === selectedTariffId) ?? items[0]
  }, [impact?.available_tariffs, selectedTariffId])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void api<TariffDeleteImpact>(`/tariffs/${tariff.id}/delete-impact`)
      .then((data) => {
        if (!cancelled) setImpact(data)
      })
      .catch((error) => {
        if (!cancelled) {
          showError(error)
          onClose()
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tariff.id, onClose])

  useEffect(() => {
    if (!impact?.can_remediate || !impact.suggested_replacement) {
      setSelectedTariffId('')
    } else {
      setSelectedTariffId(impact.suggested_replacement.id)
    }
    if (impact?.can_remediate) {
      setApplyRemediation(true)
    }
  }, [impact?.can_remediate, impact?.suggested_replacement, impact?.available_tariffs])

  const deleteBlocked =
    Boolean(impact?.last_tariff) ||
    Boolean(impact && impact.org_count > 0 && (!applyRemediation || !selectedTariff))

  async function confirm() {
    setBusy(true)
    try {
      let remediation: TariffRemediationPayload | undefined
      if (applyRemediation && impact?.can_remediate && selectedTariff) {
        remediation = { tariff_id: selectedTariff.id }
      }
      await onConfirm({ remediation })
      onClose()
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  const bannerMessage = (() => {
    if (!impact) return ''
    if (impact.last_tariff) return t('instance.tariffImpactLastTariff')
    if (impact.org_count > 0 && !impact.can_remediate) return t('instance.tariffImpactNoReplacement')
    if (impact.org_count > 0) return t('instance.tariffImpactOrgsBlocking', { count: impact.org_count })
    return t('instance.workerImpactNoImpact')
  })()

  return (
    <Modal
      onClose={() => {
        if (busy) return
        onClose()
      }}
      closeOnBackdrop={!busy && !loading}
      wide
      title={t('instance.tariffDeleteTitle', { name: tariff.name })}
      panelClassName="worker-impact-modal max-h-[min(92vh,880px)] overflow-y-auto sm:max-w-3xl"
      footer={
        <>
          <Button type="button" variant="outline" disabled={busy || loading} autoFocus onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={loading || busy || deleteBlocked}
            onClick={() => void confirm()}
          >
            {busy ? t('instance.workerImpactDeleting') : t('instance.workerDeleteConfirm')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {loading ? (
          <div className="worker-impact-banner loading" aria-busy="true">
            <p>{t('instance.workerImpactLoading')}</p>
          </div>
        ) : null}

        {!loading && impact ? (
          <>
            <div className={`worker-impact-banner ${impact.blocking ? 'warn' : 'ok'}`}>
              <p>{bannerMessage}</p>
            </div>

            {impact.org_count > 0 ? (
              <section className="worker-impact-section">
                <div className="worker-impact-section-head">
                  <h3>{t('instance.tariffImpactOrgsTitle')}</h3>
                  <p className="muted worker-impact-section-hint">{t('instance.tariffImpactOrgsHint')}</p>
                </div>
                {(impact.affected_orgs ?? []).length ? (
                  <ul className="worker-impact-list">
                    {(impact.affected_orgs ?? []).map((org) => (
                      <li key={org.id} className="worker-impact-row">
                        <span className="worker-impact-org-name">{truncateLabel(org.name, 48)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted worker-impact-empty">{t('instance.tariffImpactOrgsEmpty')}</p>
                )}
              </section>
            ) : null}

            {impact.can_remediate && selectedTariff ? (
              <section className="worker-impact-remediation">
                <div className="worker-impact-section-head">
                  <h3>{t('instance.tariffImpactRemediationTitle')}</h3>
                  <p className="muted worker-impact-section-hint">{t('instance.tariffImpactRemediationHint')}</p>
                </div>
                <AppCheckboxRow
                  id="tariff-impact-remediation-apply"
                  className="worker-impact-remediation-apply"
                  label={t('instance.tariffImpactRemediationApply')}
                  checked={applyRemediation}
                  disabled={busy}
                  onCheckedChange={setApplyRemediation}
                />
                <AppSelectField
                  className="worker-impact-remediation-pair"
                  label={t('instance.tariffImpactRemediationTariffLabel')}
                  htmlFor="tariff-impact-replacement"
                  value={selectedTariffId}
                  disabled={busy || !applyRemediation}
                  onValueChange={setSelectedTariffId}
                  options={(impact.available_tariffs ?? []).map((item) => {
                    const suggested = item.id === suggestedId
                    return {
                      value: item.id,
                      label: `${item.name}${suggested ? ` — ${t('instance.workerImpactRemediationSuggested')}` : ''}`,
                    }
                  })}
                />
              </section>
            ) : null}
          </>
        ) : null}
      </div>
    </Modal>
  )
}
