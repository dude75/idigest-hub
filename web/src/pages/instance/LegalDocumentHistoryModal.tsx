import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../../api'
import { Modal } from '../../components/Modal'
import { Segmented } from '../../components/Segmented'
import { MarkdownBody } from '../../markdown'
import {
  LEGAL_DOC_LOCALES,
  LEGAL_DOCUMENT_I18N,
  type LegalDocLocale,
  type LegalDocumentKey,
} from '../../legalDocuments'
import type { LegalDocumentVersionDetail, LegalDocumentVersionSummary } from '../../types'
import { formatDateTime } from '../../util/datetimeFormat'
import { showError } from '../../util'
import { Button } from '@/components/ui/button'
import {
  AdminDataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  adminTableCellActions,
  adminTableCellMuted,
  adminTableHeadActions,
} from '../../components/app/AdminDataTable'
import { AdminMetaRow, AdminRowActions, HubBadge } from '../../components/app/AdminUi'

type Props = {
  documentKey: LegalDocumentKey
  onClose: () => void
}

export function LegalDocumentHistoryModal({ documentKey, onClose }: Props) {
  const { t, i18n } = useTranslation()
  const [items, setItems] = useState<LegalDocumentVersionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<LegalDocumentVersionDetail | null>(null)
  const [detailBusy, setDetailBusy] = useState(false)
  const [viewLang, setViewLang] = useState<LegalDocLocale>('ru')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void api<{ items: LegalDocumentVersionSummary[] }>(
      `/instance/legal-documents/${documentKey}/versions`,
    )
      .then((data) => {
        if (!cancelled) setItems(data.items)
      })
      .catch(showError)
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [documentKey])

  async function openVersion(version: number) {
    setDetailBusy(true)
    try {
      const data = await api<LegalDocumentVersionDetail>(
        `/instance/legal-documents/${documentKey}/versions/${version}`,
      )
      setDetail(data)
    } catch (e) {
      showError(e)
    } finally {
      setDetailBusy(false)
    }
  }

  const detailText = useMemo(() => {
    if (!detail) return ''
    if (viewLang === 'ru') return detail.text_ru || detail.text_en || detail.text_es || ''
    if (viewLang === 'es') return detail.text_es || detail.text_en || detail.text_ru || ''
    return detail.text_en || detail.text_ru || detail.text_es || ''
  }, [detail, viewLang])

  const listTitle = t('instance.legalDocumentHistoryTitle', {
    document: t(`legalDocuments.tabs.${LEGAL_DOCUMENT_I18N[documentKey]}`),
  })

  if (detail) {
    return (
      <Modal
        wide
        onClose={() => setDetail(null)}
        title={t('instance.legalDocumentHistoryView', { version: detail.version })}
        description={
          <>
            {formatDateTime(detail.created_at, undefined, i18n.language)}
            {detail.created_by_email ? ` · ${detail.created_by_email}` : ''}
            {!detail.published ? ` · ${t('instance.legalDocumentHidden')}` : ''}
          </>
        }
        footer={
          <Button type="button" variant="outline" onClick={() => setDetail(null)}>
            {t('instance.legalDocumentHistoryBack')}
          </Button>
        }
      >
        <Segmented
          variant="outline"
          ariaLabel={t('instance.legalDocumentLanguage')}
          value={viewLang}
          onChange={setViewLang}
          options={LEGAL_DOC_LOCALES.map((value) => ({
            value,
            label: t(`lang.${value}`),
          }))}
        />
        <div className="agreement-text agreement-preview legal-doc-history-body max-h-[50vh] overflow-y-auto rounded-md border p-4">
          {detailText.trim() ? (
            <MarkdownBody text={detailText} />
          ) : (
            <p className="text-sm text-muted-foreground">{t('agreement.empty')}</p>
          )}
        </div>
      </Modal>
    )
  }

  return (
    <Modal wide onClose={onClose} title={listTitle}>
      {loading ? (
        <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('instance.legalDocumentHistoryEmpty')}</p>
      ) : (
        <AdminDataTable>
          <TableHeader>
            <TableRow>
              <TableHead>{t('instance.legalDocumentVersionCol')}</TableHead>
              <TableHead>{t('common.date')}</TableHead>
              <TableHead>{t('instance.legalDocumentHistoryAuthor')}</TableHead>
              <TableHead className={adminTableHeadActions} />
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((row) => (
              <TableRow key={row.version}>
                <TableCell>
                  <AdminMetaRow>
                    <HubBadge tone="muted">{row.version}</HubBadge>
                    {!row.published ? (
                      <HubBadge tone="pending">{t('instance.legalDocumentHidden')}</HubBadge>
                    ) : null}
                  </AdminMetaRow>
                </TableCell>
                <TableCell className={adminTableCellMuted}>
                  {formatDateTime(row.created_at, undefined, i18n.language)}
                </TableCell>
                <TableCell>{row.created_by_email || '—'}</TableCell>
                <TableCell className={adminTableCellActions}>
                  <AdminRowActions>
                    <Button type="button" size="sm" variant="outline" disabled={detailBusy} onClick={() => void openVersion(row.version)}>
                      {t('common.view')}
                    </Button>
                  </AdminRowActions>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </AdminDataTable>
      )}
    </Modal>
  )
}
