import type { ReactElement } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { I18nTestProvider } from './I18nTestProvider'
import i18n from '@/i18n'

export async function renderWithI18n(ui: ReactElement, options?: RenderOptions) {
  await i18n.changeLanguage('en')
  return render(<I18nTestProvider>{ui}</I18nTestProvider>, options)
}
