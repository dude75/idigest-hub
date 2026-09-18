import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'
import { AuthPageShell } from '../components/AuthPageShell'
import { Modal } from '../components/Modal'
import { resolveAuthBlockPath, resolveAuthContinuationPath } from '../routes'
import { showError } from '../util'

export function AcceptAgreementPage() {
  const { t } = useTranslation()
  const { ready, me, refresh, logout } = useAuth()
  const nav = useNavigate()
  const [accepted, setAccepted] = useState(false)
  const [busy, setBusy] = useState(false)

  if (!ready) return <p className="page muted">{t('common.loading')}</p>
  if (!me) return <Navigate to="/login" replace />

  const block = resolveAuthBlockPath(me)
  if (block === '/change-password') return <Navigate to="/change-password" replace />
  if (block === '/enroll-2fa') return <Navigate to="/enroll-2fa" replace />
  if (block === '/login') return <Navigate to="/login" replace />
  if (!me.user_agreement_required) {
    return <Navigate to={resolveAuthContinuationPath(me)} replace />
  }

  const text = me.user_agreement?.text || ''

  async function onAccept() {
    if (!accepted) return
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
        panelClassName="agreement-modal"
      >
        <header className="agreement-head">
          <h2>{t('agreement.title')}</h2>
          <p className="muted agreement-lead">{t('agreement.lead')}</p>
        </header>

        <div className="modal-body">
          <div className="agreement-text">{text || t('agreement.empty')}</div>
        </div>

        <label className="row agreement-accept">
          <input
            type="checkbox"
            checked={accepted}
            disabled={busy}
            onChange={(e) => setAccepted(e.target.checked)}
          />
          <span>{t('agreement.acceptLabel')}</span>
        </label>

        <div className="row modal-actions agreement-actions">
          <button type="button" disabled={busy} onClick={() => void logout()}>
            {t('nav.logout')}
          </button>
          <button
            className="primary"
            type="button"
            disabled={!accepted || busy}
            onClick={() => void onAccept()}
          >
            {t('agreement.continue')}
          </button>
        </div>
      </Modal>
    </AuthPageShell>
  )
}
