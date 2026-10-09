import { type IngestExtraTagsSlot, saveIngestExtraTags } from './ingestExtraTags'

export function appendIngestUserTagsToForm(body: FormData, tags: string[]): void {
  for (const name of tags) {
    body.append('user_tags', name)
  }
}

export function resetIngestExtraTags(slot: IngestExtraTagsSlot, setter?: (names: string[]) => void): void {
  setter?.([])
  saveIngestExtraTags(slot, [])
}
