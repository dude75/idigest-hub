import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LEGAL_DOCUMENT_I18N, type LegalDocumentKey } from '../legalDocuments'
import { MarkdownBody } from '../markdown'
import { Modal } from './Modal'
import { Button } from '@/components/ui/button'
import { AppCheckboxRow } from './app/AppFormControls'

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
      <div className="legal-accept-list flex flex-col gap-3">
        {documents.map((doc) => (
          <AppCheckboxRow
            key={doc.key}
            id={`legal-accept-${doc.key}`}
            className="agreement-accept"
            checked={checked[doc.key] ?? false}
            disabled={disabled}
            onCheckedChange={(value) => onCheckedChange(doc.key, value)}
            label={
              <span>
                {t('legalDocuments.acceptPrefix')}{' '}
                <Button type="button" className="legal-doc-link" disabled={disabled} onClick={(e) => {
                    e.preventDefault()
                    setViewKey(doc.key)
                  }}
                >
                  {t(`legalDocuments.tabs.${LEGAL_DOCUMENT_I18N[doc.key]}`)}
                </Button>
              </span>
            }
          />
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
            <Button type="button" onClick={() => setViewKey(null)}>
              {t('common.close')}
            </Button>
          </div>
        </Modal>
      )}
    </>
  )
}
