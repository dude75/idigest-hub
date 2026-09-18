import { useMemo, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { LegalDocumentAcceptance } from '../components/LegalDocumentAcceptance'
import { Modal } from '../components/Modal'
import { type LegalDocumentKey } from '../legalDocuments'
import { resolveAuthBlockPath, resolveAuthContinuationPath } from '../routes'
import { showError } from '../util'

export function AcceptAgreementPage() {
  const { t } = useTranslation()
  const { ready, me, refresh, logout } = useAuth()
  const nav = useNavigate()
  const [checked, setChecked] = useState<Partial<Record<LegalDocumentKey, boolean>>>({})
  const [busy, setBusy] = useState(false)

  const pendingDocs = useMemo(
    () => (me?.legal_documents ?? []).filter((doc) => doc.pending),
    [me?.legal_documents],
  )

  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!me) return <Navigate to="/login" replace />

  const block = resolveAuthBlockPath(me)
  if (block === '/change-password') return <Navigate to="/change-password" replace />
  if (block === '/enroll-2fa') return <Navigate to="/enroll-2fa" replace />
  if (block === '/login') return <Navigate to="/login" replace />
  if (!me.user_agreement_required) {
    return <Navigate to={resolveAuthContinuationPath(me)} replace />
  }

  const allChecked = pendingDocs.length > 0 && pendingDocs.every((doc) => checked[doc.key])

  async function onAccept() {
    if (!allChecked) return
    setBusy(true)
    try {
      await api('/auth/agreement/accept', { method: 'POST' })
      const next = await refresh()
      nav(resolveAuthContinuationPath(next), { replace: true })
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthPageShell>
      <Modal
        onClose={() => {
          if (busy) return
          void logout()
        }}
        closeOnBackdrop={false}
        panelClassName="agreement-modal legal-accept-modal"
      >
        <header className="agreement-head">
          <h2>{t('agreement.title')}</h2>
          <p className="muted agreement-lead">{t('agreement.lead')}</p>
        </header>

        <div className="modal-body">
          {pendingDocs.length === 0 ? (
            <p className="muted">{t('agreement.empty')}</p>
          ) : (
            <LegalDocumentAcceptance
              documents={pendingDocs}
              checked={checked}
              disabled={busy}
              onCheckedChange={(key, value) => setChecked((prev) => ({ ...prev, [key]: value }))}
            />
          )}
        </div>

        <div className="row modal-actions agreement-actions">
          <button type="button" disabled={busy} onClick={() => void logout()}>
            {t('nav.logout')}
          </button>
          <button
            className="primary"
            type="button"
            disabled={!allChecked || busy}
            onClick={() => void onAccept()}
          >
            {t('agreement.continue')}
          </button>
        </div>
      </Modal>
    </AuthPageShell>
  )
}
