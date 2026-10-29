import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithI18n } from '@/test/render'
import { AppDuration } from './AppDuration'

describe('AppDuration', () => {
  it('renders compact clock format', async () => {
    const { unmount } = await renderWithI18n(<AppDuration sec={793} variant="compact" />)
    expect(screen.getByText('13:13')).toBeInTheDocument()
    unmount()
  })

  it('renders human duration from i18n', async () => {
    await renderWithI18n(<AppDuration sec={793} variant="human" />)
    expect(screen.getByText('13 min 13 s')).toBeInTheDocument()
  })
})
