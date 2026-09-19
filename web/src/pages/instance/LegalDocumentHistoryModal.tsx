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

  const title = t('instance.legalDocumentHistoryTitle', {
    document: t(`legalDocuments.tabs.${LEGAL_DOCUMENT_I18N[documentKey]}`),
  })

  if (detail) {
    return (
      <Modal wide onClose={() => setDetail(null)} panelClassName="stack">
        <h3>{t('instance.legalDocumentHistoryView', { version: detail.version })}</h3>
        <div className="stack">
          <p className="muted legal-doc-history-meta">
            {formatDateTime(detail.created_at, undefined, i18n.language)}
            {detail.created_by_email ? ` · ${detail.created_by_email}` : ''}
            {!detail.published ? ` · ${t('instance.legalDocumentHidden')}` : ''}
          </p>
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
          <div className="agreement-text agreement-preview legal-doc-history-body">
            {detailText.trim() ? (
              <MarkdownBody text={detailText} />
            ) : (
              <p className="muted">{t('agreement.empty')}</p>
            )}
          </div>
          <div className="row">
            <button type="button" onClick={() => setDetail(null)}>
              {t('instance.legalDocumentHistoryBack')}
            </button>
          </div>
        </div>
      </Modal>
    )
  }

  return (
    <Modal wide onClose={onClose} panelClassName="stack">
      <h3>{title}</h3>
      {loading ? (
        <p className="muted">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <p className="muted">{t('instance.legalDocumentHistoryEmpty')}</p>
      ) : (
        <div className="stats-table-wrap">
          <table className="stats-table">
            <thead>
              <tr>
                <th>{t('instance.legalDocumentVersionCol')}</th>
                <th>{t('common.date')}</th>
                <th>{t('instance.legalDocumentHistoryAuthor')}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.version}>
                  <td>
                    <span className="badge">{row.version}</span>
                    {!row.published ? (
                      <span className="badge">{t('instance.legalDocumentHidden')}</span>
                    ) : null}
                  </td>
                  <td>{formatDateTime(row.created_at, undefined, i18n.language)}</td>
                  <td>{row.created_by_email || '—'}</td>
                  <td>
                    <button type="button" disabled={detailBusy} onClick={() => void openVersion(row.version)}>
                      {t('common.view')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}
