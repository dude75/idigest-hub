import type { Me } from './types'

/** Client tone flag for transcribe/import/capture requests. */
export function requestTone(me: Me | null | undefined): boolean {
  if (!me?.org?.tariff.tone_analytics_enabled) return false
  return me.user.tone_analytics_enabled ?? true
}

export function toneAnalyticsLabelKey(me: Me | null | undefined): 'library.pipeline.toneOn' | 'library.pipeline.toneOff' {
  return requestTone(me) ? 'library.pipeline.toneOn' : 'library.pipeline.toneOff'
}
