import { normalizeUserTagName, userTagNameErrorKey } from './constants/userTags'

export type IngestExtraTagsSlot = 'link' | 'file' | 'mic'

const LEGACY_STORAGE_KEY = 'idigest-ingest-extra-tags'

const STORAGE_KEYS: Record<IngestExtraTagsSlot, string> = {
  link: 'idigest-ingest-extra-tags-link',
  file: 'idigest-ingest-extra-tags-file',
  mic: 'idigest-ingest-extra-tags-mic',
}

function parseStoredTagNames(raw: string | null): string[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    const out: string[] = []
    const seen = new Set<string>()
    for (const item of parsed) {
      if (typeof item !== 'string') continue
      if (userTagNameErrorKey(item)) continue
      const name = normalizeUserTagName(item)
      const key = name.toLowerCase()
      if (seen.has(key)) continue
      seen.add(key)
      out.push(name)
    }
    return out
  } catch {
    return []
  }
}

function migrateLegacyLinkTags(): string[] {
  const legacy = localStorage.getItem(LEGACY_STORAGE_KEY)
  if (legacy === null) return []
  localStorage.setItem(STORAGE_KEYS.link, legacy)
  localStorage.removeItem(LEGACY_STORAGE_KEY)
  return parseStoredTagNames(legacy)
}

export function loadIngestExtraTags(slot: IngestExtraTagsSlot = 'link'): string[] {
  const stored = localStorage.getItem(STORAGE_KEYS[slot])
  if (slot === 'link' && stored === null) {
    return migrateLegacyLinkTags()
  }
  return parseStoredTagNames(stored)
}

export function saveIngestExtraTags(slot: IngestExtraTagsSlot, names: string[]): void {
  localStorage.setItem(STORAGE_KEYS[slot], JSON.stringify(names))
}
