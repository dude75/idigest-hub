import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import es from './locales/es.json'
import ru from './locales/ru.json'

const LOCALES = ['en', 'ru', 'es'] as const

function storedLocale(): string {
  const raw = localStorage.getItem('locale')
  if (raw && (LOCALES as readonly string[]).includes(raw)) return raw
  return 'en'
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
    es: { translation: es },
  },
  lng: storedLocale(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
export { LOCALES }
