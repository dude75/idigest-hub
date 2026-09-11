import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

type Props = {
  message: string
  confirmLabel?: string
  danger?: boolean
  busy?: boolean
  onConfirm: () => void
  onClose: () => void
}

export function ConfirmDialog({ message, confirmLabel, danger, busy, onConfirm, onClose }: Props) {
  const { t } = useTranslation()

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !busy) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, busy])

  return (
    <div className="modal-back" onClick={busy ? undefined : onClose}>
      <div
        className="card modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-message"
      >
        <p id="confirm-dialog-message">{message}</p>
        <div className="row" style={{ marginTop: 12 }}>
          <button
            type="button"
            className={danger ? 'danger' : 'primary'}
            disabled={busy}
            onClick={() => void onConfirm()}
          >
            {confirmLabel ?? t('common.confirm')}
          </button>
          <button type="button" disabled={busy} autoFocus onClick={onClose}>
            {t('common.cancel')}
          </button>
        </div>
      </div>
    </div>
  )
}
