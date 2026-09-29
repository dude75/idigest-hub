import type { ComponentProps, ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** Primary/secondary actions in forms — left-aligned, not stretched in `.stack` grids. */
export function AppFormActions({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>{children}</div>
  )
}

type SubmitButtonProps = Omit<ComponentProps<typeof Button>, 'variant' | 'disabled'> & {
  /** When false, button stays disabled (gray) until the form has valid changes to apply. */
  ready: boolean
  busy?: boolean
}

/** Primary save/create — same enabled/disabled styling across the app. */
export function AppSubmitButton({ ready, busy = false, className, type = 'button', ...props }: SubmitButtonProps) {
  return (
    <Button type={type} variant="default" disabled={!ready || busy} className={className} {...props} />
  )
}
