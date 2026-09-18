import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { AdminPage, AdminTableCard } from '../../components/AdminSection'
import { StatCard, StatGrid } from '../../components/StatCard'
import type { Tariff } from '../../types'
import { formatBytes, formatDecimal, formatInteger, showError } from '../../util'
import { emptyTariff, MAX_UPLOAD } from './constants'

export function InstanceTariffsTab() {
  const { t } = useTranslation()
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [tform, setTform] = useState(emptyTariff)
  const [editT, setEditT] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)

  async function load() {
    try {
      setTariffs((await api<{ items: Tariff[] }>('/tariffs')).items)
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const summary = useMemo(() => ({
    active: tariffs.filter((tr) => !tr.archived).length,
    archived: tariffs.filter((tr) => tr.archived).length,
    orgs: tariffs.reduce((sum, tr) => sum + (tr.org_count ?? 0), 0),
    signup: tariffs.filter((tr) => tr.available_on_signup && !tr.archived).length,
  }), [tariffs])

  async function saveTariff() {
    const body = { ...tform, max_upload_bytes: Math.min(Number(tform.max_upload_bytes) || MAX_UPLOAD, MAX_UPLOAD) }
    if (editT) {
      await api(`/tariffs/${editT}`, { method: 'PATCH', body: JSON.stringify(body) })
    } else {
      await api('/tariffs', { method: 'POST', body: JSON.stringify(body) })
    }
    setTform(emptyTariff)
    setEditT(null)
    setFormOpen(false)
    await load()
  }

  function startEdit(tr: Tariff) {
    setEditT(tr.id)
    setFormOpen(true)
    setTform({
      name: tr.name,
      unlimited: tr.unlimited,
      available_on_signup: tr.available_on_signup,
      price_per_audio_sec: tr.price_per_audio_sec,
      price_per_summarize_job: tr.price_per_summarize_job,
      price_per_1k_summary_chars: tr.price_per_1k_summary_chars,
      audio_retention_days: tr.audio_retention_days,
      api_enabled: tr.api_enabled,
      signup_credit: tr.signup_credit,
      max_upload_bytes: tr.max_upload_bytes,
    })
  }

  function cancelEdit() {
    setEditT(null)
    setTform(emptyTariff)
    setFormOpen(false)
  }

  return (
    <AdminPage>
      <StatGrid>
        <StatCard label={t('instance.tariffsActive')} value={formatInteger(summary.active)} tone="transcribe" />
        <StatCard label={t('instance.tariffsArchived')} value={formatInteger(summary.archived)} tone="ops" />
        <StatCard label={t('instance.tariffsSignup')} value={formatInteger(summary.signup)} tone="summarize" />
        <StatCard label={t('instance.orgCount')} value={formatInteger(summary.orgs)} tone="amount" />
      </StatGrid>

      <details
        className="fold org-fold org-create-fold card"
        open={formOpen}
        onToggle={(e) => setFormOpen(e.currentTarget.open)}
      >
        <summary className="org-fold-summary">
          <span>{editT ? t('instance.tariffEdit') : t('instance.tariffCreate')}</span>
        </summary>
        <div className="stack fold-body">
        <label>{t('common.name')}<input value={tform.name} onChange={(e) => setTform({ ...tform, name: e.target.value })} /></label>
        <label className="row">
          <input type="checkbox" checked={tform.unlimited} onChange={(e) => setTform({ ...tform, unlimited: e.target.checked })} />
          {t('instance.unlimited')}
        </label>
        <label className="row">
          <input type="checkbox" checked={tform.available_on_signup} onChange={(e) => setTform({ ...tform, available_on_signup: e.target.checked })} />
          {t('instance.signup')}
        </label>
        <label>{t('instance.priceAudio')}<input value={tform.price_per_audio_sec} onChange={(e) => setTform({ ...tform, price_per_audio_sec: e.target.value })} /></label>
        <label>{t('instance.priceJob')}<input value={tform.price_per_summarize_job} onChange={(e) => setTform({ ...tform, price_per_summarize_job: e.target.value })} /></label>
        <label>{t('instance.priceText')}<input value={tform.price_per_1k_summary_chars} onChange={(e) => setTform({ ...tform, price_per_1k_summary_chars: e.target.value })} /></label>
        <label>{t('instance.retentionDays')}<input type="number" min={0} value={tform.audio_retention_days} onChange={(e) => setTform({ ...tform, audio_retention_days: Number(e.target.value) })} /></label>
        <label className="row">
          <input type="checkbox" checked={tform.api_enabled} onChange={(e) => setTform({ ...tform, api_enabled: e.target.checked })} />
          {t('instance.apiEnabled')}
        </label>
        <label>{t('instance.signupCredit')}<input value={tform.signup_credit} onChange={(e) => setTform({ ...tform, signup_credit: e.target.value })} /></label>
        <label>{t('instance.uploadCap')}<input type="number" max={MAX_UPLOAD} value={tform.max_upload_bytes} onChange={(e) => setTform({ ...tform, max_upload_bytes: Number(e.target.value) })} /></label>
        <div className="row">
          <button className="primary" type="button" onClick={() => void saveTariff()}>{editT ? t('common.save') : t('common.create')}</button>
          {editT ? <button type="button" onClick={cancelEdit}>{t('common.cancel')}</button> : null}
        </div>
        </div>
      </details>

      <AdminTableCard title={t('instance.tariffsList')} empty={t('common.empty')} isEmpty={tariffs.length === 0}>
        {tariffs.length > 0 ? (
          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>{t('common.name')}</th>
                  <th className="num">{t('instance.orgCount')}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {tariffs.map((tr) => (
                  <tr key={tr.id}>
                    <td>
                      <div className="tariff-name-row">
                        <strong>{tr.name}</strong>
                        <span className="item-meta">
                          {tr.unlimited && <span className="badge">{t('instance.unlimited')}</span>}
                          {tr.available_on_signup && <span className="badge out">{t('instance.signup')}</span>}
                          {tr.archived && <span className="badge warn">{t('instance.archived')}</span>}
                        </span>
                      </div>
                      <div className="muted tariff-price-line">
                        {formatDecimal(tr.price_per_audio_sec)} / {formatDecimal(tr.price_per_summarize_job)} / {formatDecimal(tr.price_per_1k_summary_chars)}
                        {' · '}
                        {formatBytes(tr.max_upload_bytes)}
                      </div>
                    </td>
                    <td className="num">{formatInteger(tr.org_count ?? 0)}</td>
                    <td className="table-actions">
                      <div className="row">
                        <button type="button" onClick={() => startEdit(tr)}>{t('common.edit')}</button>
                        {tr.archived ? (
                          <button type="button" onClick={() => void api(`/tariffs/${tr.id}/unarchive`, { method: 'POST' }).then(load)}>{t('instance.unarchive')}</button>
                        ) : (
                          <button type="button" onClick={() => void api(`/tariffs/${tr.id}/archive`, { method: 'POST' }).then(load)}>{t('instance.archive')}</button>
                        )}
                        <button type="button" className="danger" onClick={() => void api(`/tariffs/${tr.id}`, { method: 'DELETE' }).then(load).catch(showError)}>{t('common.delete')}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </AdminTableCard>
    </AdminPage>
  )
}
