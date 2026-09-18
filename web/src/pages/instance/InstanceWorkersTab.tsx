import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { AdminPage, AdminTableCard } from '../../components/AdminSection'
import { StatCard, StatGrid } from '../../components/StatCard'
import { WorkerHealthBadge, isWorkerHealthy, isWorkerUnhealthy } from '../../components/WorkerHealthBadge'
import type { Worker } from '../../types'
import { formatInteger, showError } from '../../util'
import { emptyWorker } from './constants'

export function InstanceWorkersTab() {
  const { t } = useTranslation()
  const [workers, setWorkers] = useState<Worker[]>([])
  const [wform, setWform] = useState(emptyWorker)
  const [editW, setEditW] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)

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

  const summary = useMemo(() => ({
    total: workers.length,
    enabled: workers.filter((w) => w.enabled).length,
    healthy: workers.filter((w) => isWorkerHealthy(w)).length,
    unhealthy: workers.filter((w) => isWorkerUnhealthy(w)).length,
  }), [workers])

  async function saveWorker() {
    const body = { ...wform, weight: Number(wform.weight) }
    if (editW) {
      await api(`/workers/${editW}`, { method: 'PATCH', body: JSON.stringify(body) })
    } else {
      await api('/workers', { method: 'POST', body: JSON.stringify(body) })
    }
    setWform(emptyWorker)
    setEditW(null)
    setFormOpen(false)
    await load()
  }

  function startEdit(w: Worker) {
    setEditW(w.id)
    setFormOpen(true)
    setWform({
      type: w.type,
      name: w.name,
      base_url: w.base_url,
      api_token: '',
      weight: w.weight,
      enabled: w.enabled,
    })
  }

  function cancelEdit() {
    setEditW(null)
    setWform(emptyWorker)
    setFormOpen(false)
  }

  return (
    <AdminPage>
      <StatGrid>
        <StatCard label={t('instance.workersTotal')} value={formatInteger(summary.total)} tone="ops" />
        <StatCard label={t('instance.workersEnabled')} value={formatInteger(summary.enabled)} tone="audio" />
        <StatCard label={t('instance.workersHealthy')} value={formatInteger(summary.healthy)} tone="transcribe" />
        <StatCard label={t('instance.workersUnhealthy')} value={formatInteger(summary.unhealthy)} tone="amount" />
      </StatGrid>

      <details
        className="fold org-fold org-create-fold card"
        open={formOpen}
        onToggle={(e) => setFormOpen(e.currentTarget.open)}
      >
        <summary className="org-fold-summary">
          <span>{editW ? t('instance.workerEdit') : t('instance.workerCreate')}</span>
        </summary>
        <div className="stack fold-body">
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
        <div className="row">
          <button className="primary" type="button" onClick={() => void saveWorker()}>{editW ? t('common.save') : t('common.create')}</button>
          {editW ? <button type="button" onClick={cancelEdit}>{t('common.cancel')}</button> : null}
        </div>
        </div>
      </details>

      <AdminTableCard title={t('instance.workersList')} empty={t('common.empty')} isEmpty={workers.length === 0}>
        {workers.length > 0 ? (
          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>{t('common.name')}</th>
                  <th>{t('instance.type')}</th>
                  <th>{t('instance.weight')}</th>
                  <th>{t('instance.enabled')}</th>
                  <th>{t('instance.health')}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {workers.map((w) => (
                  <tr key={w.id}>
                    <td>{w.name || w.base_url}</td>
                    <td>{t(`task.type.${w.type}`, { defaultValue: w.type })}</td>
                    <td className="num">{formatInteger(w.weight)}</td>
                    <td>{w.enabled ? t('common.yes') : t('common.no')}</td>
                    <td><WorkerHealthBadge worker={w} /></td>
                    <td className="table-actions">
                      <div className="row">
                        <button type="button" onClick={() => startEdit(w)}>{t('common.edit')}</button>
                        <button type="button" className="danger" onClick={() => void api(`/workers/${w.id}`, { method: 'DELETE' }).then(load)}>{t('common.delete')}</button>
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
