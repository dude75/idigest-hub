import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { LEGAL_DOCUMENT_I18N, legalDocPath, type PublicLegalDocument } from '../legalDocuments'
import { MarkdownBody } from '../markdown'

type LandingLegalPayload = {
  items: PublicLegalDocument[]
  footer_text: string | null
}

export function LandingFooter() {
  const { t, i18n } = useTranslation()
  const [docs, setDocs] = useState<PublicLegalDocument[]>([])
  const [footerText, setFooterText] = useState<string | null>(null)

  useEffect(() => {
    api<LandingLegalPayload>('/public/legal-documents')
      .then((r) => {
        setDocs(r.items)
        setFooterText(r.footer_text?.trim() || null)
      })
      .catch(() => {
        setDocs([])
        setFooterText(null)
      })
  }, [i18n.language])

  if (docs.length === 0 && !footerText) return null

  return (
    <footer className="landing-footer">
      {docs.length > 0 ? (
        <nav className="landing-footer-links" aria-label={t('landing.footerLegal')}>
          {docs.map((doc) => (
            <Link key={doc.key} to={legalDocPath(doc.key)}>
              {t(`legalDocuments.tabs.${LEGAL_DOCUMENT_I18N[doc.key]}`)}
            </Link>
          ))}
        </nav>
      ) : null}
      {footerText ? (
        <div className="landing-footer-extra agreement-text">
          <MarkdownBody text={footerText} />
        </div>
      ) : null}
    </footer>
  )
}
