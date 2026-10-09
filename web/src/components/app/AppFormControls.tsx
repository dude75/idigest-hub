import { forwardRef, type ReactNode } from 'react'
import { AppField } from './AppField'
import { AppSelect, type AppSelectOption } from './AppSelect'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

type FieldProps = {
  label: ReactNode
  htmlFor: string
  description?: ReactNode
  error?: ReactNode
}

export const AppInputField = forwardRef<
  HTMLInputElement,
  FieldProps & React.ComponentProps<typeof Input>
>(function AppInputField({ label, htmlFor, description, error, className, ...props }, ref) {
  return (
    <AppField label={label} htmlFor={htmlFor} description={description} error={error}>
      <Input ref={ref} id={htmlFor} className={cn(className)} {...props} />
    </AppField>
  )
})

export type { AppSelectOption }

export function AppSelectField({
  label,
  htmlFor,
  description,
  error,
  className,
  options,
  ...props
}: FieldProps &
  Omit<React.ComponentProps<typeof AppSelect>, 'id' | 'options' | 'aria-invalid'> & {
    options: AppSelectOption[]
  }) {
  return (
    <AppField label={label} htmlFor={htmlFor} description={description} error={error}>
      <AppSelect
        id={htmlFor}
        className={className}
        options={options}
        aria-invalid={error ? true : undefined}
        {...props}
      />
    </AppField>
  )
}

type CheckboxRowProps = {
  id: string
  label: ReactNode
  checked: boolean
  disabled?: boolean
  onCheckedChange: (checked: boolean) => void
  className?: string
}

export { AppDateField } from './AppDateField'

export function AppCheckboxRow({ id, label, checked, disabled, onCheckedChange, className }: CheckboxRowProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Checkbox
        id={id}
        checked={checked}
        disabled={disabled}
        onCheckedChange={(v) => onCheckedChange(Boolean(v))}
      />
      <Label htmlFor={id} className="font-normal text-foreground">
        {label}
      </Label>
    </div>
  )
}
