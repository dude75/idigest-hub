import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithI18n } from '@/test/renderWithI18n'
import { AppListPagination } from './AppListPagination'
import type { ListPageSize } from './selectOptions'

async function renderPagination(overrides: {
  page?: number
  pageSize?: ListPageSize
  total?: number
  setPage?: ReturnType<typeof vi.fn>
  setPageSize?: ReturnType<typeof vi.fn>
} = {}) {
  const setPage = overrides.setPage ?? vi.fn()
  const setPageSize = overrides.setPageSize ?? vi.fn()
  const props = {
    htmlFor: 'list-page-size',
    page: overrides.page ?? 0,
    pageSize: overrides.pageSize ?? 10,
    total: overrides.total ?? 25,
    setPage,
    setPageSize,
  }
  await renderWithI18n(<AppListPagination {...props} />)
  return { setPage, setPageSize, props }
}

afterEach(() => {
  cleanup()
})

describe('AppListPagination', () => {
  it('shows rows-per-page label and range counter', async () => {
    await renderPagination({ page: 1, total: 25 })
    expect(screen.getByText('Rows per page')).toBeInTheDocument()
    expect(screen.getByText('11–20 of 25')).toBeInTheDocument()
  })

  it('wires page size select to label id', async () => {
    await renderPagination()
    expect(screen.getByLabelText('Rows per page')).toHaveAttribute('id', 'list-page-size')
  })

  it('disables previous on the first page', async () => {
    await renderPagination({ page: 0, total: 25 })
    expect(screen.getByRole('button', { name: 'Go to previous page' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Go to next page' })).toBeEnabled()
  })

  it('disables next on the last page', async () => {
    await renderPagination({ page: 2, total: 25 })
    expect(screen.getByRole('button', { name: 'Go to previous page' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Go to next page' })).toBeDisabled()
  })

  it('calls setPage when prev/next clicked', async () => {
    const { setPage } = await renderPagination({ page: 1, total: 25 })
    setPage.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Go to previous page' }))
    expect(setPage).toHaveBeenCalledWith(0)

    fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }))
    expect(setPage).toHaveBeenCalledWith(2)
  })

  it('shows counter on a single page when total fits page size', async () => {
    await renderPagination({ page: 0, total: 5, pageSize: 10 })
    expect(screen.getByText('1–5 of 5')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Go to next page' })).toBeDisabled()
  })
})
