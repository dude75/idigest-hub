import { XIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { userTagBadgeClassName } from './userTagBadgeStyles'

type AssignedProps = {
  name: string
  disabled?: boolean
  removeLabel: string
  onRemove: () => void
}

export function UserTagChipAssigned({ name, disabled, removeLabel, onRemove }: AssignedProps) {
  return (
    <Badge
      variant="outline"
      className={cn('user-tag-chip-assigned h-6 gap-1 pr-1', userTagBadgeClassName)}
    >
      <span className="max-w-[10rem] truncate">{name}</span>
      <button
        type="button"
        disabled={disabled}
        aria-label={removeLabel}
        className={cn(
          'inline-flex shrink-0 items-center justify-center rounded-sm border-0 bg-transparent p-0',
          'text-muted-foreground hover:text-foreground disabled:pointer-events-none disabled:opacity-50',
        )}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onRemove()
        }}
      >
        <XIcon className="size-3" data-icon="inline-end" strokeWidth={2} aria-hidden />
      </button>
    </Badge>
  )
}
