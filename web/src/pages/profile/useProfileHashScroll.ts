import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { scrollToProfileAnchor } from '../../profile/scrollToAnchor'

/** Scroll to a profile in-page anchor after tab/content is ready (sticky topbar). */
export function useProfileHashScroll(anchorId: string, ready = true, rerunWhen?: unknown) {
  const location = useLocation()

  useEffect(() => {
    if (!ready || location.hash !== `#${anchorId}`) return

    scrollToProfileAnchor(anchorId)
    const t1 = window.setTimeout(() => scrollToProfileAnchor(anchorId), 150)
    const t2 = window.setTimeout(() => scrollToProfileAnchor(anchorId), 450)

    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
    }
  }, [anchorId, location.hash, ready, rerunWhen])
}
