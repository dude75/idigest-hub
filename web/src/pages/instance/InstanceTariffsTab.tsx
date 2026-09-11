import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import type { Tariff } from '../../types'
import { showError } from '../../util'
import { emptyTariff, MAX_UPLOAD } from './constants'

export function InstanceTariffsTab() {
  const { t } = useTranslation()
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [tform, setTform] = useState(emptyTariff)
  const [editT, setEditT] = useState<string | null>(null)

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

  async function saveTariff() {
    const body = { ...tform, max_upload_bytes: Math.min(Number(tform.max_upload_bytes) || MAX_UPLOAD, MAX_UPLOAD) }
    if (editT) {
      await api(`/tariffs/${editT}`, { method: 'PATCH', body: JSON.stringify(body) })
    } else {
      await api('/tariffs', { method: 'POST', body: JSON.stringify(body) })
    }
    setTform(emptyTariff)
    setEditT(null)
    await load()
  }

  return (
    <>
      <div className="card stack">
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
        <button className="primary" type="button" onClick={() => void saveTariff()}>{editT ? t('common.save') : t('common.create')}</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>{t('common.name')}</th>
            <th>{t('instance.orgCount')}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {tariffs.map((tr) => (
            <tr key={tr.id}>
              <td>
                {tr.name} {tr.unlimited && <span className="badge">{t('instance.unlimited')}</span>}
                {tr.available_on_signup && <span className="badge out">{t('instance.signup')}</span>}
                {tr.archived && <span className="badge warn">{t('instance.archived')}</span>}
                <div className="muted">{tr.price_per_audio_sec} / {tr.price_per_summarize_job} / {tr.price_per_1k_summary_chars} · {tr.max_upload_bytes}</div>
              </td>
              <td>{tr.org_count ?? 0}</td>
              <td className="row">
                <button type="button" onClick={() => {
                  setEditT(tr.id)
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
                }}>{t('common.edit')}</button>
                {tr.archived ? (
                  <button type="button" onClick={() => void api(`/tariffs/${tr.id}/unarchive`, { method: 'POST' }).then(load)}>{t('instance.unarchive')}</button>
                ) : (
                  <button type="button" onClick={() => void api(`/tariffs/${tr.id}/archive`, { method: 'POST' }).then(load)}>{t('instance.archive')}</button>
                )}
                <button type="button" className="danger" onClick={() => void api(`/tariffs/${tr.id}`, { method: 'DELETE' }).then(load).catch(showError)}>{t('common.delete')}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
