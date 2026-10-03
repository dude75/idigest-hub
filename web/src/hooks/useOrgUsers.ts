import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { SchemaOrgUserListResponse } from '../openapi'
import type { User } from '../types'
import { showError } from '../util'

export function useOrgUsers(enabled = true) {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    if (!enabled) {
      setUsers([])
      return []
    }
    setLoading(true)
    try {
      const response = await api<SchemaOrgUserListResponse>('/org/users')
      setUsers(response.items)
      return response.items
    } catch (err) {
      showError(err)
      setUsers([])
      return []
    } finally {
      setLoading(false)
    }
  }, [enabled])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return { users, loading, refresh }
}
