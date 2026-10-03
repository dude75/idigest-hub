import type { LibraryListEnvelope } from './openapi/contracts'
import type { LibraryTab } from './routes'
import type { Audio, Summary, Transcript } from './types'

export type LibraryListResponse<T> = LibraryListEnvelope<T>

export type LibraryListQuery = {
  includeHidden?: boolean
  tag?: string | null
  ownerUserId?: string
  q?: string
  groupBySource?: boolean
  limit?: number
  offset?: number
}

export type LibrarySourceGroup<T> = {
  source_id: string | null
  items: T[]
}

export function libraryListPath(tab: LibraryTab, query: LibraryListQuery): string {
  const base =
    tab === 'audio' ? '/audios' : tab === 'transcripts' ? '/transcripts' : '/summaries'
  const params = new URLSearchParams()
  if (query.includeHidden) params.set('include_hidden', 'true')
  if (query.tag) params.set('tag', query.tag)
  if (query.ownerUserId) params.set('owner_user_id', query.ownerUserId)
  if (query.q) params.set('q', query.q)
  if (query.groupBySource) params.set('group_by', 'source')
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null && query.offset > 0) params.set('offset', String(query.offset))
  const qs = params.toString()
  return qs ? `${base}?${qs}` : base
}

export function librarySearchHaystack(tab: LibraryTab, item: Audio | Transcript | Summary): string {
  if (tab === 'audio') {
    const a = item as Audio
    return [a.filename, a.owner_email || ''].join(' ').toLowerCase()
  }
  if (tab === 'transcripts') {
    const tr = item as Transcript
    return [tr.display_title, tr.title, tr.source_filename, tr.owner_email].filter(Boolean).join(' ').toLowerCase()
  }
  const s = item as Summary
  return [s.display_title, s.title, s.source_transcript_title, s.owner_email].filter(Boolean).join(' ').toLowerCase()
}

export function filterLibraryItems<T extends { owner_user_id: string }>(
  items: T[],
  tab: LibraryTab,
  query: string,
  userId: string,
): T[] {
  const q = query.trim().toLowerCase()
  return items.filter((item) => {
    if (userId && item.owner_user_id !== userId) return false
    if (!q) return true
    return librarySearchHaystack(tab, item as unknown as Audio | Transcript | Summary).includes(q)
  })
}

/** Transcripts/summaries can group by source on the server (paginated by group). */
export function libraryServerSourceGrouping(tab: LibraryTab, groupListBySource: boolean): boolean {
  return groupListBySource && (tab === 'transcripts' || tab === 'summaries')
}
