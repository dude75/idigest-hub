import { describe, expect, it } from 'vitest'
import { filterLibraryItems, libraryListPath, libraryServerSourceGrouping } from './libraryList'
import type { Audio } from './types'

describe('libraryListPath', () => {
  it('adds pagination and owner filter params', () => {
    expect(
      libraryListPath('audio', {
        includeHidden: true,
        tag: 'mic',
        ownerUserId: 'u1',
        q: 'meet',
        limit: 10,
        offset: 20,
      }),
    ).toBe('/audios?include_hidden=true&tag=mic&owner_user_id=u1&q=meet&limit=10&offset=20')
  })
})

describe('libraryServerSourceGrouping', () => {
  it('is true for transcripts/summaries when grouping enabled', () => {
    expect(libraryServerSourceGrouping('audio', true)).toBe(false)
    expect(libraryServerSourceGrouping('transcripts', false)).toBe(false)
    expect(libraryServerSourceGrouping('transcripts', true)).toBe(true)
    expect(libraryServerSourceGrouping('summaries', true)).toBe(true)
  })
})

describe('libraryListPath group_by', () => {
  it('adds group_by=source when requested', () => {
    expect(libraryListPath('transcripts', { groupBySource: true, limit: 10 })).toBe(
      '/transcripts?group_by=source&limit=10',
    )
  })
})

describe('filterLibraryItems', () => {
  const rows: Audio[] = [
    {
      id: '1',
      org_id: 'o',
      owner_user_id: 'a',
      filename: 'hello.mp3',
      source_url: null,
      duration_sec: 1,
      created_at: '2026-01-01T00:00:00Z',
    },
    {
      id: '2',
      org_id: 'o',
      owner_user_id: 'b',
      filename: 'other.mp3',
      source_url: null,
      duration_sec: 1,
      created_at: '2026-01-01T00:00:00Z',
    },
  ]

  it('filters by owner and query', () => {
    const byOwner = filterLibraryItems(rows, 'audio', '', 'a')
    expect(byOwner.map((r) => r.id)).toEqual(['1'])
    const byQuery = filterLibraryItems(rows, 'audio', 'other', '')
    expect(byQuery.map((r) => r.id)).toEqual(['2'])
  })
})
