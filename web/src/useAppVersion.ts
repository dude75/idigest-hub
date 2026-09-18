import { useEffect, useState } from 'react'
import { api } from './api'

let cached: string | null = null

export function useAppVersion(): string | null {
  const [version, setVersion] = useState<string | null>(cached)

  useEffect(() => {
    if (cached) return
    api<{ version?: string }>('/health')
      .then((r) => {
        cached = r.version?.trim() || null
        setVersion(cached)
      })
      .catch(() => {})
  }, [])

  return version
}
