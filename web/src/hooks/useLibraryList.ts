import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  libraryListPath,
  type LibraryListResponse,
  type LibrarySourceGroup,
} from '../libraryList'
import type { LibraryTab } from '../routes'
import type { Audio, Summary, Transcript } from '../types'
import { showError } from '../util'

export type LibraryListItem = Audio | Transcript | Summary

export type UseLibraryListOptions = {
  tab: LibraryTab
  includeHidden: boolean
  tag: string | null
  ownerUserId?: string
  q?: string
  groupBySource?: boolean
  limit?: number
  offset?: number
  enabled: boolean
}

type LibraryListApiResponse<T> = LibraryListResponse<T> & {
  groups?: LibrarySourceGroup<T>[] | null
}

export function useLibraryList(options: UseLibraryListOptions) {
  const {
    tab,
    includeHidden,
    tag,
    ownerUserId,
    q,
    groupBySource,
    limit,
    offset,
    enabled,
  } = options

  const [items, setItems] = useState<LibraryListItem[]>([])
  const [sourceGroups, setSourceGroups] = useState<LibrarySourceGroup<LibraryListItem>[] | null>(
    null,
  )
  const [total, setTotal] = useState(0)
  const [hiddenCount, setHiddenCount] = useState(0)
  const [loading, setLoading] = useState(false)

  const reload = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    try {
      const path = libraryListPath(tab, {
        includeHidden,
        tag,
        ownerUserId,
        q,
        groupBySource,
        limit,
        offset,
      })
      const data = await api<LibraryListApiResponse<LibraryListItem>>(path)
      if (data.groups != null) {
        setSourceGroups(data.groups)
        setItems([])
      } else {
        setSourceGroups(null)
        setItems(data.items)
      }
      setTotal(typeof data.total === 'number' ? data.total : data.items.length)
      setHiddenCount(data.hidden_count ?? 0)
    } catch (e) {
      showError(e)
    } finally {
      setLoading(false)
    }
  }, [tab, includeHidden, tag, ownerUserId, q, groupBySource, limit, offset, enabled])

  useEffect(() => {
    void reload()
  }, [reload])

  return { items, total, hiddenCount, sourceGroups, loading, reload }
}
