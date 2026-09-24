import { describe, expect, it } from 'vitest'
import { diarizationOptionsForAsr, isDispatchableCombo } from './transcribeModels'
import type { TranscribeModels } from './types'

const models: TranscribeModels = {
  asr_models: ['parakeet', 'whisper'],
  diarization_models: ['nemo', 'pyannote'],
  dispatchable_pairs: [
    { asr_model: 'parakeet', diarization_model: 'nemo' },
    { asr_model: 'whisper', diarization_model: 'pyannote' },
  ],
}

describe('transcribeModels', () => {
  it('filters diarization options by ASR', () => {
    expect(diarizationOptionsForAsr(models, 'parakeet')).toEqual(['nemo'])
    expect(diarizationOptionsForAsr(models, 'whisper')).toEqual(['pyannote'])
  })

  it('detects dispatchable combinations', () => {
    expect(isDispatchableCombo(models, 'parakeet', 'nemo')).toBe(true)
    expect(isDispatchableCombo(models, 'parakeet', 'pyannote')).toBe(false)
    expect(isDispatchableCombo(models, 'parakeet', null)).toBe(true)
    expect(isDispatchableCombo(models, 'parakeet', '')).toBe(true)
    expect(isDispatchableCombo(models, 'unknown', null)).toBe(false)
  })
})
