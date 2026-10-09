import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from './pagination'

describe('pagination ui', () => {
  it('marks active page link', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationLink isActive>2</PaginationLink>
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    )
    const link = screen.getByRole('button', { name: '2' })
    expect(link).toHaveAttribute('data-active', 'true')
    expect(link).toHaveAttribute('aria-current', 'page')
    expect(link.className).toMatch(/bg-card/)
  })

  it('renders previous/next with accessible names', () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious text="Back" />
          </PaginationItem>
          <PaginationItem>
            <PaginationNext text="Forward" disabled />
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    )
    expect(screen.getByRole('button', { name: 'Go to previous page' })).toHaveTextContent('Back')
    expect(screen.getByRole('button', { name: 'Go to next page' })).toBeDisabled()
  })
})
