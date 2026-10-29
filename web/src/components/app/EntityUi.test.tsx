import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { hubReadingSurface, summaryBody } from '@/typography'
import { renderWithRouter } from '@/test/render'
import { EntityBodyCard, EntityPage, EntityPageLoading, EntityPageTitle } from './EntityUi'

afterEach(() => {
  cleanup()
})

describe('EntityPage', () => {
  it('renders back link in layout without JS offset sync', async () => {
    await renderWithRouter(
      <EntityPage backTo="/app/library/summaries">
        <EntityPageTitle>Title</EntityPageTitle>
        <div className="entity-detail-card">Content</div>
      </EntityPage>,
    )

    const layout = document.querySelector('.entity-page-layout')
    expect(layout).toBeTruthy()
    expect(layout?.getAttribute('style')).toBeNull()
    expect(document.querySelector('.entity-page-main')).toHaveClass('entity-page-main')
    expect(screen.getByRole('heading', { level: 1 })).toHaveClass('text-[1.35rem]')
    expect(screen.getByRole('link', { name: 'Back' })).toHaveClass('entity-back')
  })
})

describe('EntityPageLoading', () => {
  it('keeps entity shell and shows loading in detail card', async () => {
    await renderWithRouter(<EntityPageLoading backTo="/app/library/summaries" />)

    expect(document.querySelector('.entity-page-layout')).toBeTruthy()
    expect(document.querySelector('.entity-page-skeleton-title')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Back' })).toBeInTheDocument()
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })
})

describe('EntityBodyCard', () => {
  it('uses compact card title and renders body content', () => {
    render(
      <EntityBodyCard title="Summary body" actions={<button type="button">Edit</button>}>
        <div className={summaryBody} data-testid="reading-panel">
          Prose here
        </div>
      </EntityBodyCard>,
    )

    expect(screen.getByText('Summary body')).toHaveClass('font-medium')
    expect(screen.getByTestId('reading-panel')).toHaveClass('summary-body')
    expect(document.querySelector('.entity-body-card [data-slot="card-content"]')).toHaveClass(hubReadingSurface)
    expect(screen.getByText('Prose here')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument()
  })

  it('renders body without card header when title is omitted', () => {
    render(
      <EntityBodyCard>
        <p>Markdown body</p>
      </EntityBodyCard>,
    )

    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
    expect(screen.getByText('Markdown body')).toBeInTheDocument()
  })
})
