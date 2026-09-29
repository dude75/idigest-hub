import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type SegmentedVariant = 'segment' | 'pill' | 'outline'

type Option<T extends string> = {
  value: T
  label: string
}

type Props<T extends string> = {
  value: T | null
  onChange: (value: T) => void
  options: Option<T>[]
  variant?: SegmentedVariant
  ariaLabel?: string
}

const variantClass: Record<Exclude<SegmentedVariant, 'pill'>, string> = {
  segment: 'auth-segment',
  outline: 'profile-backup-formats',
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  variant = 'segment',
  ariaLabel,
}: Props<T>) {
  if (variant === 'pill') {
    return (
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={ariaLabel}>
        {options.map((opt) => (
          <Button
            key={opt.value}
            type="button"
            size="sm"
            variant={value === opt.value ? 'default' : 'outline'}
            aria-pressed={value === opt.value}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </Button>
        ))}
      </div>
    )
  }

  const role = variant === 'segment' ? 'tablist' : 'radiogroup'

  return (
    <div className={variantClass[variant]} role={role} aria-label={ariaLabel}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role={variant === 'segment' ? 'tab' : 'radio'}
          aria-selected={variant === 'segment' ? value === opt.value : undefined}
          aria-checked={variant === 'outline' ? value === opt.value : undefined}
          className={cn(value === opt.value && 'active')}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
