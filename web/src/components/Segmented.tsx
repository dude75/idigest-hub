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

const variantClass: Record<SegmentedVariant, string> = {
  segment: 'auth-segment',
  pill: 'preset-bar',
  outline: 'profile-backup-formats',
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  variant = 'segment',
  ariaLabel,
}: Props<T>) {
  const role = variant === 'segment' ? 'tablist' : variant === 'outline' ? 'radiogroup' : undefined

  return (
    <div className={variantClass[variant]} role={role} aria-label={ariaLabel}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role={variant === 'segment' ? 'tab' : variant === 'outline' ? 'radio' : undefined}
          aria-selected={variant === 'segment' ? value === opt.value : undefined}
          aria-checked={variant === 'outline' ? value === opt.value : undefined}
          className={value === opt.value ? 'active' : undefined}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
