import type { ReactNode } from 'react'
import { I18nextProvider } from 'react-i18next'
import i18n from '@/i18n'

/** Wraps UI under test with the app i18n instance (see renderWithI18n). */
export function I18nTestProvider({ children }: { children: ReactNode }) {
  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
}
