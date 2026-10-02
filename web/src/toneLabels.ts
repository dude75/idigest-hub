import type { TFunction } from 'i18next'

export function toneEmotionLabel(t: TFunction, key: string): string {
  const normalized = key.trim().toLowerCase()
  if (!normalized) return key
  return t(`transcript.toneEmotion.${normalized}`, { defaultValue: key })
}

export function toneLayerLabel(t: TFunction, key: string): string {
  const normalized = key.trim().toLowerCase()
  if (!normalized) return key
  return t(`transcript.toneLayer.${normalized}`, { defaultValue: key })
}

export function formatToneLayers(t: TFunction, layers: string[]): string {
  return layers.map((layer) => toneLayerLabel(t, layer)).join(', ')
}
