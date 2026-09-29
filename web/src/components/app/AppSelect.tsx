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
      <SelectContent>
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
