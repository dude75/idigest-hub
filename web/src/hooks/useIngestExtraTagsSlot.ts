import { useCallback, useState } from 'react'
import {
  type IngestExtraTagsSlot,
  loadIngestExtraTags,
  saveIngestExtraTags,
} from '../ingestExtraTags'

export function useIngestExtraTagsSlot(slot: IngestExtraTagsSlot) {
  const [tags, setTagsState] = useState(() => loadIngestExtraTags(slot))

  const setTags = useCallback(
    (names: string[]) => {
      setTagsState(names)
      saveIngestExtraTags(slot, names)
    },
    [slot],
  )

  const reset = useCallback(() => {
    setTagsState([])
    saveIngestExtraTags(slot, [])
  }, [slot])

  return { tags, setTags, reset }
}
