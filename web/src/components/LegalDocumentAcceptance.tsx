import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LEGAL_DOCUMENT_I18N, type LegalDocumentKey } from '../legalDocuments'
import { MarkdownBody } from '../markdown'
import { Modal } from './Modal'

export type LegalDocumentAcceptItem = {
  key: LegalDocumentKey
  version: number
  text: string
  pending?: boolean
}

type Props = {
  documents: LegalDocumentAcceptItem[]
  checked: Partial<Record<LegalDocumentKey, boolean>>
  onCheckedChange: (key: LegalDocumentKey, value: boolean) => void
  disabled?: boolean
}

export function LegalDocumentAcceptance({ documents, checked, onCheckedChange, disabled }: Props) {
  const { t } = useTranslation()
  const [viewKey, setViewKey] = useState<LegalDocumentKey | null>(null)
  const viewing = viewKey ? documents.find((doc) => doc.key === viewKey) : null

  return (
    <>
      <div className="legal-accept-list stack">
        {documents.map((doc) => (
          <label key={doc.key} className="row agreement-accept">
            <input
              type="checkbox"
              checked={checked[doc.key] ?? false}
              disabled={disabled}
              onChange={(e) => onCheckedChange(doc.key, e.target.checked)}
            />
            <span>
              {t('legalDocuments.acceptPrefix')}{' '}
              <button
                type="button"
                className="legal-doc-link"
                disabled={disabled}
                onClick={(e) => {
                  e.preventDefault()
                  setViewKey(doc.key)
                }}
              >
                {t(`legalDocuments.tabs.${LEGAL_DOCUMENT_I18N[doc.key]}`)}
              </button>
            </span>
          </label>
        ))}
      </div>

      {viewing && (
        <Modal onClose={() => setViewKey(null)} panelClassName="agreement-modal">
          <header className="agreement-head">
            <h2>{t(`legalDocuments.tabs.${LEGAL_DOCUMENT_I18N[viewing.key]}`)}</h2>
          </header>
          <div className="modal-body">
            <div className="agreement-text">
              {viewing.text ? <MarkdownBody text={viewing.text} /> : t('agreement.empty')}
            </div>
          </div>
          <div className="row modal-actions agreement-actions">
            <button type="button" className="primary" onClick={() => setViewKey(null)}>
              {t('common.close')}
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}
