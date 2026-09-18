import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Modal } from './Modal'

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
    <Modal onClose={onClose} closeOnBackdrop={!busy}>
      <p id="confirm-dialog-message">{message}</p>
      <div className="row modal-actions">
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
    </Modal>
  )
}
