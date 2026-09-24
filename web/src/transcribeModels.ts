import type { TranscribeModels, TranscribePrefs } from './types'

export type DispatchablePair = {
  asr_model: string
  diarization_model: string | null
}

export function dispatchablePairs(models: TranscribeModels): DispatchablePair[] {
  return models.dispatchable_pairs ?? []
}

export function diarizationOptionsForAsr(
  models: TranscribeModels,
  asrModel: string,
): string[] {
  const ids = new Set<string>()
  for (const pair of dispatchablePairs(models)) {
    if (pair.asr_model === asrModel && pair.diarization_model) {
      ids.add(pair.diarization_model)
    }
  }
  return [...ids].sort()
}

export function isDispatchableCombo(
  models: TranscribeModels,
  asrModel: string,
  diarizationModel: string | null,
): boolean {
  const diar =
    diarizationModel == null || diarizationModel === '' ? null : diarizationModel
  if (diar === null) {
    return dispatchablePairs(models).some((pair) => pair.asr_model === asrModel)
  }
  return dispatchablePairs(models).some(
    (pair) => pair.asr_model === asrModel && pair.diarization_model === diar,
  )
}

export function resolveEffectiveAsr(
  asrChoice: string,
  prefs: TranscribePrefs,
): string {
  return asrChoice === 'inherit' ? prefs.instance_asr_model : asrChoice
}

export function resolveEffectiveDiarization(
  diarChoice: 'inherit' | 'off' | string,
  prefs: TranscribePrefs,
): string | null {
  if (diarChoice === 'inherit') return prefs.instance_diarization_model
  if (diarChoice === 'off') return null
  return diarChoice
}
