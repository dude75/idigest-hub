import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { hubReadingSurface, summaryBody } from '@/typography'
import { renderWithI18n } from '@/test/renderWithI18n'
import { EntityBodyCard, EntityPage } from './EntityUi'

describe('EntityPage', () => {
  it('renders back link in layout without JS offset sync', async () => {
    await renderWithI18n(
      <MemoryRouter>
        <EntityPage backTo="/app/library/summaries">
          <h1 className="entity-title">Title</h1>
          <div className="entity-detail-card">Content</div>
        </EntityPage>
      </MemoryRouter>,
    )

    const layout = document.querySelector('.entity-page-layout')
    expect(layout).toBeTruthy()
    expect(layout?.getAttribute('style')).toBeNull()
    expect(document.querySelector('.entity-page-main')).toHaveClass('entity-page-main')
    expect(screen.getByRole('link', { name: 'Back' })).toHaveClass('entity-back')
  })
})

describe('EntityBodyCard', () => {
  it('uses compact card title and renders body content', async () => {
    await renderWithI18n(
      <EntityBodyCard title="Summary body" actions={<button type="button">Edit</button>}>
        <div className={summaryBody} data-testid="reading-panel">
          Prose here
        </div>
      </EntityBodyCard>,
    )

    expect(screen.getByText('Summary body')).toHaveClass('font-medium')
    expect(screen.getByTestId('reading-panel')).toHaveClass('summary-body')
    expect(document.querySelector('[data-slot="card-content"]')).toHaveClass(hubReadingSurface)
    expect(screen.getByText('Prose here')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument()
  })
})
