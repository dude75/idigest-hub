import { normalizeUserTagName, userTagNameErrorKey } from './constants/userTags'

const STORAGE_KEY = 'idigest-ingest-extra-tags'

export function loadIngestExtraTags(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
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

export function saveIngestExtraTags(names: string[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(names))
}
