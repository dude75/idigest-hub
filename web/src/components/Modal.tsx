import type { ReactNode } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

type Props = {
  onClose: () => void
  children?: ReactNode
  title?: ReactNode
  description?: ReactNode
  footer?: ReactNode
  wide?: boolean
  closeOnBackdrop?: boolean
  panelClassName?: string
  showCloseButton?: boolean
}

export function Modal({
  onClose,
  children,
  title,
  description,
  footer,
  wide,
  closeOnBackdrop = true,
  panelClassName,
  showCloseButton,
}: Props) {
  const showClose = showCloseButton ?? Boolean(title)

  return (
    <Dialog
      open
      disablePointerDismissal={!closeOnBackdrop}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogContent
        showCloseButton={showClose}
        className={cn(
          'gap-4 p-6 sm:max-w-lg',
          wide && 'sm:max-w-[960px]',
          panelClassName,
        )}
      >
        {title || description ? (
          <DialogHeader className="text-left">
            {title ? <DialogTitle>{title}</DialogTitle> : null}
            {description ? <DialogDescription>{description}</DialogDescription> : null}
          </DialogHeader>
        ) : null}
        {children}
        {footer ? <DialogFooter className="border-t-0 bg-transparent p-0 sm:justify-end">{footer}</DialogFooter> : null}
      </DialogContent>
    </Dialog>
  )
}
