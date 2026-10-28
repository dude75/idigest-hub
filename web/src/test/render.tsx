import type { ReactElement, ReactNode } from 'react'
import type { RenderOptions } from '@testing-library/react'
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom'
import { renderWithI18n } from './renderWithI18n'

type RouterOptions = {
  initialEntries?: MemoryRouterProps['initialEntries']
  initialIndex?: MemoryRouterProps['initialIndex']
}

/**
 * Prefer this for components that call useTranslation (wraps I18nextProvider).
 * @see I18nTestProvider
 */
export { renderWithI18n } from './renderWithI18n'
export { I18nTestProvider } from './I18nTestProvider'

export async function renderWithRouter(
  ui: ReactElement,
  options?: RenderOptions & RouterOptions,
) {
  const { initialEntries, initialIndex, ...renderOptions } = options ?? {}
  const wrapped = (
    <MemoryRouter initialEntries={initialEntries} initialIndex={initialIndex}>
      {ui}
    </MemoryRouter>
  )
  return renderWithI18n(wrapped, renderOptions)
}

export async function renderWithProviders(
  ui: ReactNode,
  options?: RenderOptions & RouterOptions,
) {
  return renderWithRouter(<>{ui}</>, options)
}
