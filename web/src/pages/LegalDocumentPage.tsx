import { useEffect, useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { BackToLandingLink } from '../components/BackToLandingLink'
import { LandingHeader } from '../components/LandingHeader'
import { LEGAL_DOCUMENT_I18N, legalDocKeyFromSlug, type PublicLegalDocument } from '../legalDocuments'
import { MarkdownBody } from '../markdown'

export function LegalDocumentPage() {
  const { slug } = useParams<{ slug: string }>()
  const { t, i18n } = useTranslation()
  const { ready, bootstrapDone } = useAuth()
  const [doc, setDoc] = useState<PublicLegalDocument | null>(null)
  const [missing, setMissing] = useState(false)
  const key = slug ? legalDocKeyFromSlug(slug) : null

  useEffect(() => {
    if (!key) {
      setMissing(true)
      return
    }
    setDoc(null)
    setMissing(false)
    api<PublicLegalDocument>(`/public/legal-documents/${key}`)
      .then(setDoc)
      .catch(() => setMissing(true))
  }, [key, i18n.language])

  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!bootstrapDone) return <Navigate to="/setup" replace />
  if (!key || missing) return <Navigate to="/" replace />
  if (!doc) return <p className="page muted">{t('common.loading')}</p>

  return (
    <div className="landing legal-document-page">
      <LandingHeader />

      <main className="legal-document-main">
        <h1>{t(`legalDocuments.tabs.${LEGAL_DOCUMENT_I18N[doc.key]}`)}</h1>
        <div className="agreement-text legal-document-body">
          {doc.text ? <MarkdownBody text={doc.text} /> : t('agreement.empty')}
        </div>
        <div className="legal-document-actions">
          <BackToLandingLink className="btn legal-document-back" />
        </div>
      </main>
    </div>
  )
}
