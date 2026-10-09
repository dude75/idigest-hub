import type { TFunction } from 'i18next'
import { ingestLinkFieldMode } from './captureHost'

export function studioLinkSubmitLabel(
  t: TFunction,
  url: string,
  busy: boolean,
  ingestToCapture: boolean,
): string {
  if (busy) {
    return ingestToCapture ? t('library.capturing') : t('library.importing')
  }
  const mode = ingestLinkFieldMode(url)
  if (mode === 'meeting') return t('ingest.linkSubmitMeeting')
  if (mode === 'import') return t('ingest.linkSubmitImport')
  return t('ingest.linkSubmitIdle')
}
