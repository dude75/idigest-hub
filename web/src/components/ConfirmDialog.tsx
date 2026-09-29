import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
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
    <Modal
      onClose={onClose}
      closeOnBackdrop={!busy}
      showCloseButton={false}
      title={t('common.confirm')}
      description={message}
      footer={
        <>
          <Button type="button" variant="outline" disabled={busy} autoFocus onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            type="button"
            variant={danger ? 'destructive' : 'default'}
            disabled={busy}
            onClick={() => void onConfirm()}
          >
            {confirmLabel ?? t('common.confirm')}
          </Button>
        </>
      }
    />
  )
}
