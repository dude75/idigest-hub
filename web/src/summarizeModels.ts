import type { SummarizeModels, SummarizePrefs } from './types'

export function resolveEffectiveSummarizeModel(
  choice: string,
  prefs: SummarizePrefs,
): string | null {
  if (choice === 'inherit') return prefs.instance_summarize_model
  return choice
}

export function isAvailableSummarizeModel(models: SummarizeModels, model: string | null): boolean {
  if (!model) return true
  if (models.summarize_models.length === 0) return true
  return models.summarize_models.includes(model)
}
