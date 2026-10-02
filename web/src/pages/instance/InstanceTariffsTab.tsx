import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '../../api'
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
  adminTableCellMuted,
  adminTableCellNum,
  adminTableCellPrimary,
  adminTableHeadActions,
  adminTableHeadNum,
} from '../../components/app/AdminDataTable'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Modal } from '../../components/Modal'
import { StatCard, StatGrid } from '../../components/StatCard'
import { TariffDetails } from '../../components/TariffDetails'
import type { Tariff } from '../../types'
import { formatBytes, formatDecimal, formatInteger, showError } from '../../util'
import { emptyTariff, MAX_UPLOAD } from './constants'
import { Button } from '@/components/ui/button'
import { AdminFormActions, AdminMetaRow, AdminRowActions, AppSubmitButton, HubBadge } from '../../components/app/AdminUi'
import { jsonDirty } from '../../util/formDirty'
import { AppCheckboxRow, AppInputField } from '../../components/app/AppFormControls'
import { cn } from '@/lib/utils'

function formToPreviewTariff(tform: typeof emptyTariff, id: string, archived: boolean): Tariff {
  return {
    id,
    name: tform.name,
    unlimited: tform.unlimited,
    available_on_signup: tform.available_on_signup,
    archived,
    price_per_audio_sec: tform.price_per_audio_sec,
    price_per_summarize_job: tform.price_per_summarize_job,
    price_per_1k_summary_chars: tform.price_per_1k_summary_chars,
    audio_retention_days: tform.audio_retention_days,
    api_enabled: tform.api_enabled,
    signup_credit: tform.signup_credit,
    max_upload_bytes: tform.max_upload_bytes,
    tone_analytics_enabled: tform.tone_analytics_enabled,
  }
}

export function InstanceTariffsTab() {
  const { t } = useTranslation()
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [tform, setTform] = useState(emptyTariff)
  const [editT, setEditT] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Tariff | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [cloneTarget, setCloneTarget] = useState<Tariff | null>(null)
  const [cloneName, setCloneName] = useState('')
  const [cloneBusy, setCloneBusy] = useState(false)
  const formRef = useRef<HTMLDivElement>(null)

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

  const editingTariff = editT ? tariffs.find((tr) => tr.id === editT) ?? null : null
  const editingArchived = Boolean(editingTariff?.archived)

  const tariffBaseline = useMemo(() => {
    if (editT && editingTariff) {
      return {
        name: editingTariff.name,
        unlimited: editingTariff.unlimited,
        available_on_signup: editingTariff.available_on_signup,
        price_per_audio_sec: editingTariff.price_per_audio_sec,
        price_per_summarize_job: editingTariff.price_per_summarize_job,
        price_per_1k_summary_chars: editingTariff.price_per_1k_summary_chars,
        audio_retention_days: editingTariff.audio_retention_days,
        api_enabled: editingTariff.api_enabled,
        signup_credit: editingTariff.signup_credit,
        max_upload_bytes: editingTariff.max_upload_bytes,
        tone_analytics_enabled: editingTariff.tone_analytics_enabled ?? false,
      }
    }
    return emptyTariff
  }, [editT, editingTariff])

  const tariffDirty = jsonDirty(tform, tariffBaseline)
  const tariffReady = tariffDirty && tform.name.trim().length > 0

  function scrollToForm() {
    requestAnimationFrame(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  function openCreate() {
    setEditT(null)
    setTform(emptyTariff)
    setFormOpen(true)
    scrollToForm()
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
      tone_analytics_enabled: tr.tone_analytics_enabled ?? false,
    })
    scrollToForm()
  }

  function cancelEdit() {
    setEditT(null)
    setTform(emptyTariff)
    setFormOpen(false)
  }

  async function saveTariff() {
    const name = tform.name.trim()
    if (!name) {
      toast.error(t('instance.tariffNameRequired'))
      return
    }
    const body = {
      ...tform,
      name,
      max_upload_bytes: Math.min(Number(tform.max_upload_bytes) || MAX_UPLOAD, MAX_UPLOAD),
    }
    setSaveBusy(true)
    try {
      if (editT) {
        await api(`/tariffs/${editT}`, { method: 'PATCH', body: JSON.stringify(body) })
      } else {
        await api('/tariffs', { method: 'POST', body: JSON.stringify(body) })
      }
      toast.success(t('profile.saved'))
      cancelEdit()
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setSaveBusy(false)
    }
  }

  function openClone(tr: Tariff) {
    setCloneTarget(tr)
    setCloneName(`${tr.name} (${t('instance.tariffCloneNameSuffix')})`)
  }

  async function confirmClone() {
    if (!cloneTarget) return
    const name = cloneName.trim()
    if (!name) {
      toast.error(t('instance.tariffNameRequired'))
      return
    }
    setCloneBusy(true)
    try {
      await api(`/tariffs/${cloneTarget.id}/clone`, { method: 'POST', body: JSON.stringify({ name }) })
      toast.success(t('profile.saved'))
      setCloneTarget(null)
      setCloneName('')
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setCloneBusy(false)
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleteBusy(true)
    try {
      await api(`/tariffs/${deleteTarget.id}`, { method: 'DELETE' })
      if (editT === deleteTarget.id) cancelEdit()
      setDeleteTarget(null)
      await load()
    } catch (e) {
      showError(e)
    } finally {
      setDeleteBusy(false)
    }
  }

  const previewTariff = formToPreviewTariff(tform, editT ?? 'preview', editingArchived)
  const cloneReady = cloneName.trim().length > 0

  useEffect(() => {
    if (!cloneTarget) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !cloneBusy) {
        setCloneTarget(null)
        setCloneName('')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cloneTarget, cloneBusy])

  return (
    <AdminPage>
      <StatGrid>
        <StatCard label={t('instance.tariffsActive')} value={formatInteger(summary.active)} tone="transcribe" />
        <StatCard label={t('instance.tariffsArchived')} value={formatInteger(summary.archived)} tone="ops" />
        <StatCard label={t('instance.tariffsSignup')} value={formatInteger(summary.signup)} tone="summarize" />
        <StatCard label={t('instance.orgCount')} value={formatInteger(summary.orgs)} tone="amount" />
      </StatGrid>

      {formOpen ? (
        <div ref={formRef}>
          <AdminFormCard title={editT ? t('instance.tariffEdit') : t('instance.tariffCreate')}>
            <AppInputField
              label={t('common.name')}
              htmlFor="tariff-name"
              value={tform.name}
              disabled={saveBusy}
              onChange={(e) => setTform({ ...tform, name: e.target.value })}
            />
            <AppCheckboxRow
              id="tariff-unlimited"
              label={t('instance.unlimited')}
              checked={tform.unlimited}
              disabled={saveBusy}
              onCheckedChange={(checked) => setTform({ ...tform, unlimited: checked })}
            />
            <AppCheckboxRow
              id="tariff-signup"
              label={t('instance.signup')}
              checked={tform.available_on_signup}
              disabled={saveBusy || editingArchived}
              onCheckedChange={(checked) => setTform({ ...tform, available_on_signup: checked })}
            />
            {editingArchived ? (
              <p className="muted">{t('instance.tariffSignupArchivedHint')}</p>
            ) : null}
            <AppInputField
              label={t('instance.priceAudio')}
              htmlFor="tariff-price-audio"
              value={tform.price_per_audio_sec}
              disabled={saveBusy}
              onChange={(e) => setTform({ ...tform, price_per_audio_sec: e.target.value })}
            />
            <AppInputField
              label={t('instance.priceJob')}
              htmlFor="tariff-price-job"
              value={tform.price_per_summarize_job}
              disabled={saveBusy}
              onChange={(e) => setTform({ ...tform, price_per_summarize_job: e.target.value })}
            />
            <AppInputField
              label={t('instance.priceText')}
              htmlFor="tariff-price-text"
              value={tform.price_per_1k_summary_chars}
              disabled={saveBusy}
              onChange={(e) => setTform({ ...tform, price_per_1k_summary_chars: e.target.value })}
            />
            <AppInputField
              label={t('instance.retentionDays')}
              htmlFor="tariff-retention"
              type="number"
              min={0}
              value={tform.audio_retention_days}
              disabled={saveBusy}
              onChange={(e) => setTform({ ...tform, audio_retention_days: Number(e.target.value) })}
            />
            <AppCheckboxRow
              id="tariff-api"
              label={t('instance.apiEnabled')}
              checked={tform.api_enabled}
              disabled={saveBusy}
              onCheckedChange={(checked) => setTform({ ...tform, api_enabled: checked })}
            />
            <AppCheckboxRow
              id="tariff-tone-analytics"
              label={t('instance.toneAnalyticsEnabled')}
              checked={tform.tone_analytics_enabled}
              disabled={saveBusy}
              onCheckedChange={(checked) => setTform({ ...tform, tone_analytics_enabled: checked })}
            />
            <AppInputField
              label={t('instance.signupCredit')}
              htmlFor="tariff-signup-credit"
              value={tform.signup_credit}
              disabled={saveBusy || tform.unlimited}
              onChange={(e) => setTform({ ...tform, signup_credit: e.target.value })}
            />
            <AppInputField
              label={t('instance.uploadCap')}
              htmlFor="tariff-upload-cap"
              type="number"
              min={1}
              max={MAX_UPLOAD}
              value={tform.max_upload_bytes}
              disabled={saveBusy}
              description={t('instance.uploadCapHint', { size: formatBytes(tform.max_upload_bytes) })}
              onChange={(e) => setTform({ ...tform, max_upload_bytes: Number(e.target.value) })}
            />
            <div>
              <p className="muted">{t('instance.tariffPreview')}</p>
              <TariffDetails tariff={previewTariff} />
            </div>
            <AdminFormActions>
              <AppSubmitButton ready={tariffReady} busy={saveBusy} onClick={() => void saveTariff()}>
                {editT ? t('common.save') : t('common.create')}
              </AppSubmitButton>
              <Button type="button" variant="outline" disabled={saveBusy} onClick={cancelEdit}>
                {t('common.cancel')}
              </Button>
            </AdminFormActions>
          </AdminFormCard>
        </div>
      ) : null}

      <AdminTableCard
        title={t('instance.tariffsList')}
        empty={t('common.empty')}
        isEmpty={tariffs.length === 0}
        tableLayout
        actions={
          <Button type="button" size="sm" onClick={openCreate}>
            {t('instance.tariffCreate')}
          </Button>
        }
      >
        {tariffs.length > 0 ? (
          <AdminDataTable>
            <TableHeader>
              <TableRow>
                <TableHead>{t('common.name')}</TableHead>
                <TableHead>{t('common.status')}</TableHead>
                <TableHead>{t('instance.tariffRatesColumn')}</TableHead>
                <TableHead className={adminTableHeadNum}>{t('instance.orgCount')}</TableHead>
                <TableHead className={adminTableHeadActions} />
              </TableRow>
            </TableHeader>
            <TableBody>
              {tariffs.map((tr) => (
                <TableRow key={tr.id} data-state={editT === tr.id ? 'selected' : undefined}>
                  <TableCell className={adminTableCellPrimary}>{tr.name}</TableCell>
                  <TableCell className={adminTableCellBadges}>
                    {tr.unlimited ||
                    tr.available_on_signup ||
                    tr.archived ||
                    editT === tr.id ? (
                      <AdminMetaRow>
                        {tr.unlimited ? <HubBadge tone="primary">{t('instance.unlimited')}</HubBadge> : null}
                        {tr.available_on_signup ? (
                          <HubBadge tone="success">{t('instance.signup')}</HubBadge>
                        ) : null}
                        {tr.archived ? <HubBadge tone="warning">{t('instance.archived')}</HubBadge> : null}
                        {editT === tr.id ? (
                          <HubBadge tone="pending">{t('instance.tariffEditing')}</HubBadge>
                        ) : null}
                      </AdminMetaRow>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell className={cn(adminTableCellMuted, 'tabular-nums')}>
                    {formatDecimal(tr.price_per_audio_sec)} / {formatDecimal(tr.price_per_summarize_job)} /{' '}
                    {formatDecimal(tr.price_per_1k_summary_chars)}
                    {' · '}
                    {formatBytes(tr.max_upload_bytes)}
                  </TableCell>
                  <TableCell className={adminTableCellNum}>{formatInteger(tr.org_count ?? 0)}</TableCell>
                  <TableCell className={adminTableCellActions}>
                    <AdminRowActions>
                      <Button
                        type="button"
                        size="sm"
                        variant={editT === tr.id ? 'secondary' : 'outline'}
                        onClick={() => startEdit(tr)}
                      >
                        {t('common.edit')}
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => openClone(tr)}>
                        {t('instance.tariffClone')}
                      </Button>
                      {tr.archived ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            void api(`/tariffs/${tr.id}/unarchive`, { method: 'POST' }).then(load).catch(showError)
                          }
                        >
                          {t('instance.unarchive')}
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            void api(`/tariffs/${tr.id}/archive`, { method: 'POST' }).then(load).catch(showError)
                          }
                        >
                          {t('instance.archive')}
                        </Button>
                      )}
                      <Button type="button" size="sm" variant="destructive" onClick={() => setDeleteTarget(tr)}>
                        {t('common.delete')}
                      </Button>
                    </AdminRowActions>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </AdminDataTable>
        ) : null}
      </AdminTableCard>

      {cloneTarget ? (
        <Modal
          onClose={() => {
            if (!cloneBusy) {
              setCloneTarget(null)
              setCloneName('')
            }
          }}
          closeOnBackdrop={!cloneBusy}
          showCloseButton={false}
          title={t('instance.tariffCloneTitle')}
          description={t('instance.tariffCloneHint', { name: cloneTarget.name })}
          footer={
            <>
              <Button
                type="button"
                variant="outline"
                disabled={cloneBusy}
                onClick={() => {
                  setCloneTarget(null)
                  setCloneName('')
                }}
              >
                {t('common.cancel')}
              </Button>
              <Button
                type="button"
                disabled={cloneBusy || !cloneReady}
                onClick={() => void confirmClone()}
              >
                {t('instance.tariffClone')}
              </Button>
            </>
          }
        >
          <AppInputField
            label={t('common.name')}
            htmlFor="tariff-clone-name"
            value={cloneName}
            disabled={cloneBusy}
            autoFocus
            onChange={(e) => setCloneName(e.target.value)}
          />
        </Modal>
      ) : null}

      {deleteTarget && (
        <ConfirmDialog
          message={t('instance.tariffDeleteConfirm', { name: deleteTarget.name })}
          confirmLabel={t('common.delete')}
          danger
          busy={deleteBusy}
          onConfirm={() => void confirmDelete()}
          onClose={() => {
            if (!deleteBusy) setDeleteTarget(null)
          }}
        />
      )}
    </AdminPage>
  )
}
