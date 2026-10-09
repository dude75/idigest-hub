import type { ReactNode } from 'react'
import type { AppSelectOption } from './AppSelect'

export const LIST_PAGE_SIZES = [5, 10, 50, 100] as const
export type ListPageSize = (typeof LIST_PAGE_SIZES)[number]
export const DEFAULT_LIST_PAGE_SIZE: ListPageSize = 10

export function allOption(label: ReactNode): AppSelectOption {
  return { value: '', label }
}

export function pageSizeOptions(sizes: readonly number[]): AppSelectOption[] {
  return sizes.map((n) => ({ value: String(n), label: String(n) }))
}

export const LIST_PAGE_SIZE_OPTIONS = pageSizeOptions(LIST_PAGE_SIZES)

/** Client-side lists: clamp page when total or page size changes. */
export function listPageBounds(total: number, page: number, pageSize: number) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  return { pageCount, safePage, offset: safePage * pageSize }
}
