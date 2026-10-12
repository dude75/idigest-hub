import { parseRecognizedIngestLink } from './captureHost'

/** Read clipboard when the user focuses the ingest URL field; null if unavailable or unrecognized. */
export async function readRecognizedIngestLinkFromClipboard(): Promise<string | null> {
  if (typeof navigator === 'undefined' || !navigator.clipboard?.readText) return null
  try {
    const text = await navigator.clipboard.readText()
    return parseRecognizedIngestLink(text)
  } catch {
    return null
  }
}
