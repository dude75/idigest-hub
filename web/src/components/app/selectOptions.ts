import type { ReactNode } from 'react'
import type { AppSelectOption } from './AppSelect'

export function allOption(label: ReactNode): AppSelectOption {
  return { value: '', label }
}

export function pageSizeOptions(sizes: readonly number[]): AppSelectOption[] {
  return sizes.map((n) => ({ value: String(n), label: String(n) }))
}
