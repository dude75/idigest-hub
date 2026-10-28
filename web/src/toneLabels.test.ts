import { beforeAll, describe, expect, it } from 'vitest'
import i18n from '@/i18n'
import { formatToneLayers, toneEmotionLabel } from './toneLabels'

describe('toneLabels', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('ru')
  })

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
