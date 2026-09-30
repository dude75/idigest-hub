import type { ReactNode } from 'react'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

export type AppSelectOption = {
  value: string
  label: ReactNode
  disabled?: boolean
}

/** Dropdown at least as wide as the trigger, can grow for long labels. */
export const appSelectExpandMenuClassName =
  'w-auto min-w-(--anchor-width) max-w-[min(22rem,calc(100vw-2.5rem))]'

/** Prefer viewport over clipping cards (e.g. library filter panel overflow-hidden). */
export const appSelectExpandMenuCollisionAvoidance = {
  side: 'flip' as const,
  align: 'shift' as const,
  fallbackAxisSide: 'none' as const,
}

function expandMenuCollisionBoundary() {
  return typeof document !== 'undefined' ? document.documentElement : undefined
}

/** Shared SelectContent props for narrow trigger + wide menu (library filters, mic modal, …). */
export function appSelectExpandMenuContentProps(className?: string) {
  return {
    side: 'bottom' as const,
    align: 'start' as const,
    alignItemWithTrigger: false as const,
    className: cn(appSelectExpandMenuClassName, className),
    collisionBoundary: expandMenuCollisionBoundary(),
    collisionAvoidance: appSelectExpandMenuCollisionAvoidance,
  }
}

type AppSelectProps = {
  id?: string
  className?: string
  disabled?: boolean
  value: string
  onValueChange: (value: string) => void
  placeholder?: string
  options: AppSelectOption[]
  size?: 'sm' | 'default'
  required?: boolean
  'aria-invalid'?: boolean
  /** Wider popup on open while the trigger can stay narrow; unified placement vs viewport. */
  expandMenu?: boolean
}

export function AppSelect({
  id,
  className,
  disabled,
  value,
  onValueChange,
  placeholder,
  options,
  size = 'default',
  required,
  'aria-invalid': ariaInvalid,
  expandMenu = false,
}: AppSelectProps) {
  const items = options.map((o) => ({ value: o.value, label: o.label }))

  return (
    <Select
      disabled={disabled}
      required={required}
      value={value === '' ? null : value}
      onValueChange={(next) => onValueChange(next ?? '')}
      items={items}
    >
      <SelectTrigger
        id={id}
        size={size}
        className={cn('w-full min-w-0', className)}
        aria-invalid={ariaInvalid}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent {...(expandMenu ? appSelectExpandMenuContentProps() : {})}>
        <SelectGroup>
          {options.map((opt) => (
            <SelectItem
              key={opt.value === '' ? '__empty' : opt.value}
              value={opt.value}
              disabled={opt.disabled}
            >
              {opt.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}
