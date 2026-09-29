import { forwardRef, type ReactNode } from 'react'
import { AppField } from './AppField'
import { AuthSelect } from '../auth/AuthSelect'
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

export function AppSelectField({
  label,
  htmlFor,
  description,
  error,
  children,
  ...props
}: FieldProps & React.ComponentProps<typeof AuthSelect>) {
  return (
    <AppField label={label} htmlFor={htmlFor} description={description} error={error}>
      <AuthSelect id={htmlFor} {...props}>
        {children}
      </AuthSelect>
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

/** Page size control: label left, select right (e.g. «Показывать» + «10»). */
export function AppPageSizeField({
  label,
  htmlFor,
  className,
  selectClassName,
  children,
  ...props
}: FieldProps & React.ComponentProps<typeof AuthSelect> & { selectClassName?: string }) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Label htmlFor={htmlFor} className="font-normal text-muted-foreground">
        {label}
      </Label>
      <AuthSelect id={htmlFor} className={cn('h-8 w-[4.5rem] shrink-0', selectClassName)} {...props}>
        {children}
      </AuthSelect>
    </div>
  )
}

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
