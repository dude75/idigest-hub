import type { ReactNode } from 'react'

type Props = {
  onClose: () => void
  children: ReactNode
  wide?: boolean
  closeOnBackdrop?: boolean
  backdropClassName?: string
  panelClassName?: string
}

export function Modal({
  onClose,
  children,
  wide,
  closeOnBackdrop = true,
  backdropClassName,
  panelClassName,
}: Props) {
  const panelClass = ['card', 'modal', wide && 'modal-wide', panelClassName].filter(Boolean).join(' ')

  return (
    <div
      className={['modal-back', backdropClassName].filter(Boolean).join(' ')}
      onClick={closeOnBackdrop ? onClose : undefined}
    >
      <div
        className={panelClass}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {children}
      </div>
    </div>
  )
}
