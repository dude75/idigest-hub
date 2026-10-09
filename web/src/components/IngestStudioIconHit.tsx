import type { KeyboardEvent } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ingestStudioHitSurfaceClassName } from './ingestStudioHitSurface'

type Props = {
  icon: LucideIcon
  disabled?: boolean
  className?: string
  ariaLabel: string
  onClick: () => void
}

/** Icon-only hit target — same DOM/CSS shell as {@link IngestStudioLinkField} (div, not button). */
export function IngestStudioIconHit({ icon: Icon, disabled, className, ariaLabel, onClick }: Props) {
  function activate() {
    if (disabled) return
    onClick()
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      activate()
    }
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      className={cn(ingestStudioHitSurfaceClassName(), 'ingest-studio-icon-hit', className)}
      aria-label={ariaLabel}
      aria-disabled={disabled || undefined}
      onClick={() => activate()}
      onKeyDown={onKeyDown}
    >
      <Icon className="ingest-studio-hit-surface-icon pointer-events-none" strokeWidth={1.25} aria-hidden="true" />
    </div>
  )
}
