import type { ReactNode } from 'react'
import { FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'

type Props = {
  label: ReactNode
  htmlFor: string
  children: ReactNode
  description?: ReactNode
  error?: ReactNode
  invalid?: boolean
}

export function AuthField({ label, htmlFor, children, description, error, invalid }: Props) {
  return (
    <div className="flex flex-col gap-2" data-invalid={invalid ? true : undefined}>
      <FieldLabel htmlFor={htmlFor}>{label}</FieldLabel>
      {children}
      {error ? <FieldError>{error}</FieldError> : description ? <FieldDescription>{description}</FieldDescription> : null}
    </div>
  )
}
