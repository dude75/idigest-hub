import { describe, expect, it } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import ru from './locales/ru.json'
import { formatToneLayers, toneEmotionLabel } from './toneLabels'

void i18n.use(initReactI18next).init({
  lng: 'ru',
  resources: { en: { translation: en }, ru: { translation: ru } },
})

describe('toneLabels', () => {
  it('localizes known emotions', () => {
    expect(toneEmotionLabel(i18n.t.bind(i18n), 'joy')).toBe('Радость')
  })

  it('falls back to raw key for unknown emotions', () => {
    expect(toneEmotionLabel(i18n.t.bind(i18n), 'custom_mood')).toBe('custom_mood')
  })

  it('localizes tone layers', () => {
    expect(formatToneLayers(i18n.t.bind(i18n), ['text', 'prosody'])).toBe('Текст, Просодия')
  })
})
