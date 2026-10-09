import type { ReactElement } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import i18n from '@/i18n'

export async function renderWithI18n(ui: ReactElement, options?: RenderOptions) {
  await i18n.changeLanguage('en')
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>, options)
}
