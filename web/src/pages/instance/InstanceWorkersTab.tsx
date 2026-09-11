import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import type { Worker } from '../../types'
import { showError } from '../../util'
import { emptyWorker } from './constants'
import { healthLabel } from './utils'

export function InstanceWorkersTab() {
  const { t } = useTranslation()
  const [workers, setWorkers] = useState<Worker[]>([])
  const [wform, setWform] = useState(emptyWorker)
  const [editW, setEditW] = useState<string | null>(null)

  async function load() {
    try {
      setWorkers((await api<{ items: Worker[] }>('/workers')).items)
    } catch (e) {
      showError(e)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function saveWorker() {
    const body = { ...wform, weight: Number(wform.weight) }
    if (editW) {
      await api(`/workers/${editW}`, { method: 'PATCH', body: JSON.stringify(body) })
    } else {
      await api('/workers', { method: 'POST', body: JSON.stringify(body) })
    }
    setWform(emptyWorker)
    setEditW(null)
    await load()
  }

  return (
    <>
      <div className="card stack">
        <label>{t('instance.type')}
          <select value={wform.type} onChange={(e) => setWform({ ...wform, type: e.target.value })}>
            <option value="transcribe">{t('instance.transcribe')}</option>
            <option value="summarize">{t('instance.summarize')}</option>
          </select>
        </label>
        <label>{t('common.name')}<input value={wform.name} onChange={(e) => setWform({ ...wform, name: e.target.value })} /></label>
        <label>{t('instance.baseUrl')}<input value={wform.base_url} onChange={(e) => setWform({ ...wform, base_url: e.target.value })} /></label>
        <label>{t('instance.apiToken')}<input value={wform.api_token} onChange={(e) => setWform({ ...wform, api_token: e.target.value })} /></label>
        <label>{t('instance.weight')}<input type="number" min={1} value={wform.weight} onChange={(e) => setWform({ ...wform, weight: Number(e.target.value) })} /></label>
        <label className="row">
          <input type="checkbox" checked={wform.enabled} onChange={(e) => setWform({ ...wform, enabled: e.target.checked })} />
          {t('instance.enabled')}
        </label>
        <button className="primary" type="button" onClick={() => void saveWorker()}>{editW ? t('common.save') : t('common.create')}</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>{t('common.name')}</th>
            <th>{t('instance.type')}</th>
            <th>{t('instance.health')}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {workers.map((w) => (
            <tr key={w.id}>
              <td>{w.name || w.base_url}</td>
              <td>{w.type} · w{w.weight} {w.enabled ? '' : `(${t('common.disable')})`}</td>
              <td>{healthLabel(w)}</td>
              <td className="row">
                <button type="button" onClick={() => { setEditW(w.id); setWform({ type: w.type, name: w.name, base_url: w.base_url, api_token: '', weight: w.weight, enabled: w.enabled }) }}>{t('common.edit')}</button>
                <button type="button" className="danger" onClick={() => void api(`/workers/${w.id}`, { method: 'DELETE' }).then(load)}>{t('common.delete')}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
