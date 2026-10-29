import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { ListRow } from './ListRow'

describe('ListRow', () => {
  it('uses shared app row title typography on links', () => {
    render(
      <MemoryRouter>
        <ListRow to="/app/audio/1" title="Example" meta="Meta line" />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: 'Example' })
    expect(link.className).toContain('text-base')
    expect(link.className).toContain('font-medium')
    expect(link.className).toContain('text-foreground')
  })

  it('marks list rows for typeset opt-out', () => {
    const { container } = render(
      <MemoryRouter>
        <ListRow title="Static" />
      </MemoryRouter>,
    )
    expect(container.querySelector('[data-slot="list-row"]')).toBeTruthy()
  })
})
