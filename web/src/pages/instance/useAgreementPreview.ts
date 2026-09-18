import { useEffect, useState } from 'react'
import { api } from '../../api'

export function useAgreementPreview(source: string): string {
  const [preview, setPreview] = useState(source)

  useEffect(() => {
    const trimmed = source.trim()
    if (!trimmed) {
      setPreview('')
      return
    }
    let cancelled = false
    const timer = window.setTimeout(() => {
      void api<{ text: string }>('/instance/settings/agreement/preview', {
        method: 'POST',
        body: JSON.stringify({ text: source }),
      })
        .then((res) => {
          if (!cancelled) setPreview(res.text)
        })
        .catch(() => {
          if (!cancelled) setPreview(source)
        })
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [source])

  return preview
}
